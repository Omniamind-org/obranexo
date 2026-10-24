"""Clientes de modelos de linguagem com interface única para o restante do sistema.

Provedores: Google Gemini (SDK `google-genai`), Groq (SDK `groq`) e Anthropic (SDK `anthropic`).
Toda chamada passa por aqui para que:
  - custo e tokens de cada análise sejam contabilizados (UsoLLM), lidos da resposta de cada API,
    com os tokens de raciocínio ("thinking") separados dos de resposta;
  - cada chamada lógica vire uma linha na trilha (observability/trilha.py): agente, modelo pedido × usado,
    latência, cache, reserva e erro — é o que permite investigar uma resposta ruim depois;
  - respostas idênticas sejam reaproveitadas do cache em disco (reprodutibilidade; temperatura 0 em todos);
  - falhas transitórias (429/503) tenham retentativa e, se persistirem, caiam para um modelo reserva;
  - os agentes dependam só de três operações: extrair (saída estruturada), texto e conversa (ferramentas).
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import re
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from obranexo.config import Config, config
from obranexo.models import UsoLLM
from obranexo.observability import logs
from obranexo.observability.trilha import ChamadaLLM, resumir, trilha

T = TypeVar("T", bound=BaseModel)

# A chamada lógica em andamento nesta thread: _contabilizar e _ler_cache completam o registro dela
_chamada_atual: contextvars.ContextVar[ChamadaLLM | None] = contextvars.ContextVar("obranexo_chamada", default=None)


class LLMIndisponivel(RuntimeError):
    pass


@dataclass
class ChamadaFerramenta:
    id: str
    nome: str
    entrada: dict[str, Any]


@dataclass
class RespostaLLM:
    texto: str = ""
    chamadas: list[ChamadaFerramenta] = field(default_factory=list)
    parada: str = "fim"  # fim | ferramentas | recusa | limite


class Conversa(ABC):
    """Uma conversa com ferramentas. O histórico fica dentro do objeto, no formato do provedor."""

    @abstractmethod
    def enviar(self, texto: str) -> RespostaLLM: ...

    @abstractmethod
    def responder_ferramentas(self, resultados: list[tuple[str, str, bool]]) -> RespostaLLM:
        """resultados: lista de (id_da_chamada, saida, is_error)."""


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class LLMClient(ABC):
    provedor: str = "nenhum"

    def __init__(self, cfg: Config | None = None, uso: UsoLLM | None = None):
        self.cfg = cfg or config
        self.uso = uso or UsoLLM()
        self.orcamento = self.cfg.orcamento_tokens  # quem cria o cliente pode ajustar (ex.: pelo nº de itens)
        self.cfg.dir_llm_cache.mkdir(parents=True, exist_ok=True)

    @property
    def disponivel(self) -> bool:
        return False

    def tokens_usados(self) -> int:
        return self.uso.tokens_entrada + self.uso.tokens_saida + self.uso.tokens_raciocinio

    def excedeu_orcamento(self, desde: int = 0, limite: int | None = None) -> bool:
        """Sem argumentos: orçamento total do cliente. Com `desde`/`limite`: orçamento de um trecho (ex.: um agente)."""
        return (self.tokens_usados() - desde) > (limite if limite is not None else self.orcamento)

    # ------------------------------------------------------------ cache

    def _chave(self, payload: dict[str, Any]) -> Path:
        bruto = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()
        return self.cfg.dir_llm_cache / f"{hashlib.sha256(bruto).hexdigest()}.json"

    def _ler_cache(self, chave: Path, modelo: str | None = None) -> dict[str, Any] | None:
        if self.cfg.llm_cache and chave.exists():
            reg = _chamada_atual.get()
            if reg is not None:
                reg.cache_hit = True
                reg.modelo_usado = modelo or reg.modelo_pedido
            return json.loads(chave.read_text(encoding="utf-8"))
        return None

    def _gravar_cache(self, chave: Path, dados: dict[str, Any]) -> None:
        if self.cfg.llm_cache:
            chave.write_text(json.dumps(dados, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    # ------------------------------------------------------------ trilha

    @contextmanager
    def _chamada(self, operacao: str, modelo: str, entrada: str = "") -> Iterator[ChamadaLLM]:
        """Uma chamada lógica: mede a latência de ponta a ponta (com retentativas e reserva), consolida os
        tokens que _contabilizar for recebendo e grava a linha na trilha, inclusive quando falha."""
        reg = ChamadaLLM.nova(operacao, self.provedor, modelo, entrada)
        token = _chamada_atual.set(reg)
        inicio = time.perf_counter()
        try:
            yield reg
        except Exception as exc:
            reg.status = "erro"
            reg.erro = f"{type(exc).__name__}: {str(exc)[:300]}"
            raise
        finally:
            _chamada_atual.reset(token)
            reg.latencia_ms = int((time.perf_counter() - inicio) * 1000)
            reg.reserva = bool(reg.modelo_usado and reg.modelo_usado != reg.modelo_pedido)
            with LLMClient._lock_uso:
                self.uso.latencia_ms += reg.latencia_ms
                self.uso.chamadas_cache += int(reg.cache_hit)
                self.uso.chamadas_reserva += int(reg.reserva)
            try:
                trilha.gravar(reg)
            except Exception as exc:  # observabilidade nunca derruba uma análise
                logs.registrar("trilha_indisponivel", erro=f"{type(exc).__name__}: {exc}")

    # ------------------------------------------------------------ custo

    _lock_uso = threading.Lock()  # extrações rodam em paralelo; a contagem precisa ser atômica

    def _contabilizar(self, modelo: str, entrada: int, saida: int, cache_leitura: int = 0, cache_escrita: int = 0, raciocinio: int = 0) -> None:
        with LLMClient._lock_uso:
            self._contabilizar_sem_lock(modelo, entrada, saida, cache_leitura, cache_escrita, raciocinio)

    def _contabilizar_sem_lock(self, modelo: str, entrada: int, saida: int, cache_leitura: int, cache_escrita: int, raciocinio: int = 0) -> None:
        # Raciocínio é cobrado como saída nos três provedores; escrita de cache (só Anthropic) custa 1,25× a entrada
        preco_in, preco_out, preco_cache = self.cfg.precos_usd.get(modelo, (0.0, 0.0, 0.0))
        custo = (entrada * preco_in + cache_escrita * preco_in * 1.25 + cache_leitura * preco_cache + (saida + raciocinio) * preco_out) / 1_000_000
        self.uso.chamadas += 1
        self.uso.tokens_entrada += entrada + cache_escrita
        self.uso.tokens_saida += saida
        self.uso.tokens_raciocinio += raciocinio
        self.uso.tokens_cache_leitura += cache_leitura
        self.uso.custo_usd = round(self.uso.custo_usd + custo, 6)
        pm = self.uso.por_modelo.setdefault(modelo, {"chamadas": 0, "entrada": 0, "saida": 0, "raciocinio": 0})
        pm["chamadas"] += 1
        pm["entrada"] += entrada + cache_escrita + cache_leitura
        pm["saida"] += saida
        pm["raciocinio"] = pm.get("raciocinio", 0) + raciocinio
        reg = _chamada_atual.get()
        if reg is not None:  # uma chamada lógica pode somar várias respostas (retentativa, reserva)
            reg.modelo_usado = modelo
            reg.tokens_entrada += entrada
            reg.tokens_saida += saida
            reg.tokens_raciocinio += raciocinio
            reg.tokens_cache_leitura += cache_leitura
            reg.tokens_cache_escrita += cache_escrita
            reg.custo_usd += custo

    # ------------------------------------------------------------ fallback

    # Após falhar (429/503/timeout), o modelo fica fora por 10 min em TODO o processo — compartilhado
    # entre análises, para o servidor não voltar a esperar um modelo sobrecarregado a cada requisição.
    _QUARENTENA_S = 600.0
    _indisponiveis: dict[str, float] = {}

    def _candidatos(self, modelo: str) -> list[str]:
        agora = time.time()
        lista = [modelo] + [m for m in self.cfg.modelos_reserva if m != modelo]
        ativos = [m for m in lista if LLMClient._indisponiveis.get(m, 0) < agora]
        return ativos or lista

    def _com_reserva(self, modelo: str, fn):
        """Executa fn(candidato) no modelo pedido ou, se ele estiver indisponível, nos reservas.
        Devolve (resultado, modelo_que_respondeu)."""
        ultimo: Exception | None = None
        for candidato in self._candidatos(modelo):
            try:
                return fn(candidato), candidato
            except LLMIndisponivel as exc:
                LLMClient._indisponiveis[candidato] = time.time() + self._QUARENTENA_S
                ultimo = exc
                continue
        raise ultimo or LLMIndisponivel("nenhum modelo disponível")

    # ------------------------------------------------------------ interface

    @abstractmethod
    def extrair(self, modelo: str, system: str, prompt: str, schema: type[T], max_tokens: int = 8000) -> T: ...

    @abstractmethod
    def texto(self, modelo: str, system: str, prompt: str, max_tokens: int = 4000) -> str: ...

    @abstractmethod
    def conversa(self, modelo: str, system: str, tools: list[dict[str, Any]]) -> Conversa: ...


class ClienteNulo(LLMClient):
    """Sem provedor configurado: o fluxo roda em modo determinístico."""

    def extrair(self, *a, **k):
        raise LLMIndisponivel("nenhum provedor de LLM configurado")

    def texto(self, *a, **k):
        raise LLMIndisponivel("nenhum provedor de LLM configurado")

    def conversa(self, *a, **k):
        raise LLMIndisponivel("nenhum provedor de LLM configurado")


# ---------------------------------------------------------------------------
# Google Gemini
# ---------------------------------------------------------------------------

_TRANSIENTES = {429, 500, 502, 503, 504}


def _schema_para_gemini(schema: dict[str, Any]) -> dict[str, Any]:
    """Converte o JSON Schema neutro (estilo Anthropic strict) para o subconjunto aceito pelo Gemini:
    sem strict/additionalProperties e com `nullable` no lugar de type: [..., "null"]."""
    out: dict[str, Any] = {}
    for k, v in schema.items():
        if k in {"strict", "additionalProperties", "$schema", "title"}:
            continue
        if k == "type" and isinstance(v, list):
            tipos = [t for t in v if t != "null"]
            out["type"] = tipos[0] if tipos else "string"
            if "null" in v:
                out["nullable"] = True
        elif k == "properties":
            out[k] = {p: _schema_para_gemini(s) for p, s in v.items()}
        elif k == "items" and isinstance(v, dict):
            out[k] = _schema_para_gemini(v)
        else:
            out[k] = v
    return out


class GeminiClient(LLMClient):
    provedor = "gemini"

    def __init__(self, cfg: Config | None = None, uso: UsoLLM | None = None):
        super().__init__(cfg, uso)
        from google import genai
        from google.genai import types

        # Sem timeout, uma chamada ao modelo sobrecarregado chegou a levar 275 s; com ele, cai para o reserva
        self._client = genai.Client(api_key=self.cfg.gemini_api_key, http_options=types.HttpOptions(timeout=int(self.cfg.llm_timeout_s * 1000)))

    @property
    def disponivel(self) -> bool:
        return bool(self.cfg.gemini_api_key)

    def _gerar(self, modelo: str, contents: Any, config_extra: dict[str, Any]) -> Any:
        """generate_content com retentativas para 429/503 e espera crescente."""
        import httpx
        from google.genai import errors, types

        cfg = types.GenerateContentConfig(temperature=0, **config_extra)  # temperatura 0: mesma entrada, mesma saída
        # Poucas tentativas: se o modelo está sobrecarregado (503) ou sem cota (429), o reserva
        # responde em segundos e o modelo principal entra em quarentena nesta sessão.
        esperas = (3.0, 6.0)
        for tentativa in range(len(esperas) + 1):
            try:
                if self.cfg.llm_pausa_s:
                    time.sleep(self.cfg.llm_pausa_s)
                return self._client.models.generate_content(model=modelo, contents=contents, config=cfg)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                # Timeout já é longo: não repete no mesmo modelo, vai direto para o reserva
                raise LLMIndisponivel(f"{modelo}: sem resposta em {self.cfg.llm_timeout_s:.0f}s ({type(exc).__name__})") from exc
            except errors.APIError as exc:
                codigo = getattr(exc, "code", None)
                if codigo in _TRANSIENTES and tentativa < len(esperas):
                    time.sleep(esperas[tentativa])
                    continue
                if codigo in _TRANSIENTES or codigo == 404:
                    raise LLMIndisponivel(f"{modelo}: HTTP {codigo} — {str(exc)[:160]}") from exc
                raise
        raise LLMIndisponivel(f"{modelo}: esgotadas as tentativas")

    def _contabilizar_resposta(self, modelo: str, resposta: Any) -> None:
        um = getattr(resposta, "usage_metadata", None)
        if um is None:
            return
        entrada = int(getattr(um, "prompt_token_count", 0) or 0)
        saida = int(getattr(um, "candidates_token_count", 0) or 0)
        raciocinio = int(getattr(um, "thoughts_token_count", 0) or 0)  # o Gemini separa o "thinking" da resposta
        cache = int(getattr(um, "cached_content_token_count", 0) or 0)
        self._contabilizar(modelo, entrada - cache, saida, cache_leitura=cache, raciocinio=raciocinio)

    @staticmethod
    def _parada(candidato: Any) -> str:
        motivo = str(getattr(candidato, "finish_reason", "") or "").upper()
        if "SAFETY" in motivo or "BLOCK" in motivo or "PROHIBITED" in motivo:
            return "recusa"
        if "MAX_TOKENS" in motivo:
            return "limite"
        return "fim"

    def extrair(self, modelo: str, system: str, prompt: str, schema: type[T], max_tokens: int = 8000) -> T:
        def _run(m: str) -> T:
            payload = {"op": "extrair", "provedor": "gemini", "modelo": m, "system": system, "prompt": prompt, "schema": schema.model_json_schema()}
            chave = self._chave(payload)
            cache = self._ler_cache(chave, m)
            if cache is not None:
                return schema.model_validate(cache["parsed"])
            resposta = self._gerar(
                m, prompt, {"system_instruction": system, "response_mime_type": "application/json", "response_schema": schema, "max_output_tokens": max_tokens}
            )
            self._contabilizar_resposta(m, resposta)
            parsed = getattr(resposta, "parsed", None)
            if parsed is None:
                texto = (getattr(resposta, "text", None) or "").strip()
                if not texto:
                    raise LLMIndisponivel(f"{m}: resposta vazia na saída estruturada")
                parsed = schema.model_validate_json(texto)
            if not isinstance(parsed, schema):
                parsed = schema.model_validate(parsed)
            self._gravar_cache(chave, {"parsed": parsed.model_dump(mode="json")})
            return parsed

        with self._chamada("extrair", modelo, prompt) as reg:
            parsed = self._com_reserva(modelo, _run)[0]
            reg.saida_resumo = resumir(parsed.model_dump_json())
            return parsed

    def texto(self, modelo: str, system: str, prompt: str, max_tokens: int = 4000) -> str:
        def _run(m: str) -> str:
            payload = {"op": "texto", "provedor": "gemini", "modelo": m, "system": system, "prompt": prompt}
            chave = self._chave(payload)
            cache = self._ler_cache(chave, m)
            if cache is not None:
                return cache["texto"]
            resposta = self._gerar(m, prompt, {"system_instruction": system, "max_output_tokens": max_tokens})
            self._contabilizar_resposta(m, resposta)
            texto = (getattr(resposta, "text", None) or "").strip()
            self._gravar_cache(chave, {"texto": texto})
            return texto

        with self._chamada("texto", modelo, prompt) as reg:
            texto = self._com_reserva(modelo, _run)[0]
            reg.saida_resumo = resumir(texto)
            return texto

    def conversa(self, modelo: str, system: str, tools: list[dict[str, Any]]) -> Conversa:
        return _ConversaGemini(self, modelo, system, tools)


def _resumo_resposta(resposta: RespostaLLM) -> str | None:
    """Texto da rodada ou, quando o modelo só pediu ferramentas, os nomes delas."""
    if resposta.texto:
        return resumir(resposta.texto)
    return resumir(", ".join(f"{c.nome}({json.dumps(c.entrada, ensure_ascii=False, default=str)[:80]})" for c in resposta.chamadas))


class _ConversaGemini(Conversa):
    def __init__(self, cliente: GeminiClient, modelo: str, system: str, tools: list[dict[str, Any]]):
        from google.genai import types

        self.c = cliente
        self.modelo = modelo
        self.system = system
        self.tool = types.Tool(
            function_declarations=[
                types.FunctionDeclaration(name=t["name"], description=t.get("description", ""), parameters=_schema_para_gemini(t["input_schema"]))
                for t in tools
            ]
        )
        self.historico: list[Any] = []
        self._nomes: dict[str, str] = {}
        self._ultima_entrada = ""

    def _rodada(self) -> RespostaLLM:
        with self.c._chamada("conversa", self.modelo, self._ultima_entrada) as reg:
            resposta = self._rodada_sem_trilha()
            reg.saida_resumo = _resumo_resposta(resposta)
            return resposta

    def _rodada_sem_trilha(self) -> RespostaLLM:
        from google.genai import types

        payload = {"op": "conversa", "provedor": "gemini", "modelo": self.modelo, "system": self.system,
                   "historico": [h.model_dump(mode="json", exclude_none=True) for h in self.historico]}
        chave = self.c._chave(payload)
        cache = self.c._ler_cache(chave, self.modelo)
        if cache is not None:
            conteudo = types.Content.model_validate(cache["content"])
            parada = cache.get("parada", "fim")
        else:
            def _run(m: str):
                return self.c._gerar(m, self.historico, {"system_instruction": self.system, "tools": [self.tool]})

            resposta, modelo_usado = self.c._com_reserva(self.modelo, _run)
            self.c._contabilizar_resposta(modelo_usado, resposta)
            if not resposta.candidates:
                return RespostaLLM(texto="", parada="recusa")
            cand = resposta.candidates[0]
            conteudo = cand.content
            parada = GeminiClient._parada(cand)
            self.c._gravar_cache(chave, {"content": conteudo.model_dump(mode="json", exclude_none=True), "parada": parada})
        self.historico.append(conteudo)
        chamadas: list[ChamadaFerramenta] = []
        texto = ""
        for parte in conteudo.parts or []:
            if getattr(parte, "function_call", None):
                fc = parte.function_call
                cid = fc.id or f"fc-{uuid.uuid4().hex[:8]}"
                self._nomes[cid] = fc.name
                chamadas.append(ChamadaFerramenta(id=cid, nome=fc.name, entrada=dict(fc.args or {})))
            elif getattr(parte, "text", None) and not getattr(parte, "thought", False):
                texto += parte.text
        if chamadas and parada == "fim":
            parada = "ferramentas"
        return RespostaLLM(texto=texto.strip(), chamadas=chamadas, parada=parada)

    def enviar(self, texto: str) -> RespostaLLM:
        from google.genai import types

        self.historico.append(types.Content(role="user", parts=[types.Part.from_text(text=texto)]))
        self._ultima_entrada = texto
        return self._rodada()

    def responder_ferramentas(self, resultados: list[tuple[str, str, bool]]) -> RespostaLLM:
        from google.genai import types

        partes = [
            types.Part.from_function_response(name=self._nomes.get(cid, cid), response={"erro": saida} if erro else {"resultado": saida})
            for cid, saida, erro in resultados
        ]
        self.historico.append(types.Content(role="user", parts=partes))
        self._ultima_entrada = _resumo_resultados(resultados)
        return self._rodada()


def _resumo_resultados(resultados: list[tuple[str, str, bool]]) -> str:
    return "resultado de ferramenta(s): " + " | ".join(("ERRO " if erro else "") + saida[:120] for _, saida, erro in resultados)


# ---------------------------------------------------------------------------
# Groq (API no formato OpenAI, SDK `groq`)
# ---------------------------------------------------------------------------
#
# Particularidades tratadas aqui:
#  - ferramentas no formato OpenAI ({"type": "function", "function": {...}}); os argumentos chegam como
#    STRING JSON; resultados voltam como mensagens role="tool" com tool_call_id;
#  - saída estruturada: json_schema existe só em alguns modelos (gpt-oss, Llama 4, Kimi); nos demais o
#    pedido é recusado com 400 e caímos para json_object, que exige a palavra "JSON" na conversa — o
#    esquema vai no system prompt e a resposta é validada por Pydantic, com uma nova tentativa se falhar;
#  - 400 "tool_use_failed" / "json_validate_failed": o modelo gerou chamada/JSON malformado — tentamos de
#    novo uma vez e, persistindo, o modelo reserva assume;
#  - 413: o pedido é maior que o limite de tokens por minuto do plano (comum no nível gratuito);
#  - 403 "Access denied. Please check your network settings": bloqueio de rede/região do Groq (antes da
#    autenticação) — mensagem clara e reserva;
#  - modelos de raciocínio: gpt-oss aceita reasoning_effort; Qwen 3 pode devolver <think>…</think>.

_RE_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)


def _tools_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""), "parameters": t["input_schema"]}} for t in tools]


def _json_da_resposta(texto: str) -> str:
    """Tira raciocínio (<think>) e cercas de código, e isola o objeto JSON."""
    t = _RE_THINK.sub("", texto or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I).strip()
    ini, fim = t.find("{"), t.rfind("}")
    return t[ini : fim + 1] if ini >= 0 and fim > ini else t


def _codigo_erro_groq(exc: Exception) -> str:
    corpo = getattr(exc, "body", None)
    if isinstance(corpo, dict):
        erro = corpo.get("error", corpo)
        if isinstance(erro, dict) and erro.get("code"):
            return str(erro["code"])
    return str(exc)


class GroqClient(LLMClient):
    provedor = "groq"

    def __init__(self, cfg: Config | None = None, uso: UsoLLM | None = None):
        super().__init__(cfg, uso)
        import groq

        self._client = groq.Groq(api_key=self.cfg.groq_api_key, timeout=self.cfg.llm_timeout_s, max_retries=2)
        self._sem_json_schema: set[str] = set()  # modelos que recusaram response_format json_schema

    @property
    def disponivel(self) -> bool:
        return bool(self.cfg.groq_api_key)

    @staticmethod
    def _extras(modelo: str) -> dict[str, Any]:
        if modelo.startswith("openai/gpt-oss"):
            return {"reasoning_effort": "low"}
        if modelo.startswith("qwen/"):
            return {"reasoning_format": "hidden"}
        return {}

    def _criar(self, modelo: str, **kwargs: Any) -> Any:
        """chat.completions.create com os erros do Groq traduzidos para indisponibilidade (=> reserva)."""
        import groq

        if self.cfg.llm_pausa_s:
            time.sleep(self.cfg.llm_pausa_s)
        try:
            resposta = self._client.chat.completions.create(model=modelo, **self._extras(modelo), **kwargs)
        except groq.PermissionDeniedError as exc:
            raise LLMIndisponivel(f"{modelo}: o Groq recusou o acesso desta rede (403 — bloqueio de rede/região do provedor, não da chave)") from exc
        except groq.AuthenticationError as exc:
            raise LLMIndisponivel(f"{modelo}: chave do Groq inválida (401)") from exc
        except groq.RateLimitError as exc:
            raise LLMIndisponivel(f"{modelo}: limite de requisições/tokens do Groq atingido (429)") from exc
        except groq.NotFoundError as exc:
            raise LLMIndisponivel(f"{modelo}: modelo não encontrado ou descontinuado no Groq (404)") from exc
        except (groq.APITimeoutError, groq.APIConnectionError) as exc:
            raise LLMIndisponivel(f"{modelo}: sem resposta do Groq ({type(exc).__name__})") from exc
        except groq.APIStatusError as exc:
            if exc.status_code == 413:
                raise LLMIndisponivel(f"{modelo}: pedido maior que o limite de tokens por minuto do plano (413)") from exc
            if exc.status_code >= 500:
                raise LLMIndisponivel(f"{modelo}: erro do Groq (HTTP {exc.status_code})") from exc
            raise
        u = getattr(resposta, "usage", None)
        if u is not None:
            # No formato OpenAI o raciocínio vem dentro de completion_tokens; o detalhe, quando existe, permite separá-lo
            detalhes = getattr(u, "completion_tokens_details", None)
            raciocinio = int(getattr(detalhes, "reasoning_tokens", 0) or 0) if detalhes is not None else 0
            saida = int(getattr(u, "completion_tokens", 0) or 0)
            self._contabilizar(modelo, int(getattr(u, "prompt_tokens", 0) or 0), max(saida - raciocinio, 0), raciocinio=raciocinio)
        return resposta

    def extrair(self, modelo: str, system: str, prompt: str, schema: type[T], max_tokens: int = 8000) -> T:
        import groq
        from pydantic import ValidationError

        esquema = schema.model_json_schema()

        def _run(m: str) -> T:
            payload = {"op": "extrair", "provedor": "groq", "modelo": m, "system": system, "prompt": prompt, "schema": esquema}
            chave = self._chave(payload)
            cache = self._ler_cache(chave, m)
            if cache is not None:
                return schema.model_validate(cache["parsed"])
            usa_schema = m not in self._sem_json_schema
            mensagens = [
                {"role": "system", "content": system + "\n\nResponda APENAS com um objeto JSON válido que siga este esquema JSON:\n"
                 + json.dumps(esquema, ensure_ascii=False)},
                {"role": "user", "content": prompt},
            ]
            for tentativa in range(3):
                fmt = {"type": "json_schema", "json_schema": {"name": schema.__name__, "schema": esquema, "strict": False}} if usa_schema else {"type": "json_object"}
                try:
                    resp = self._criar(m, messages=mensagens, response_format=fmt, temperature=0, max_completion_tokens=min(max_tokens, 32000))
                except groq.BadRequestError as exc:
                    codigo = _codigo_erro_groq(exc)
                    if usa_schema and ("json_schema" in codigo or "response_format" in codigo or "json_schema" in str(exc)):
                        self._sem_json_schema.add(m)  # este modelo não tem json_schema: segue com json_object
                        usa_schema = False
                        continue
                    if "json_validate_failed" in codigo and tentativa < 2:
                        continue  # o modelo gerou JSON malformado: tenta de novo
                    raise LLMIndisponivel(f"{m}: pedido recusado pelo Groq ({codigo[:160]})") from exc
                texto = resp.choices[0].message.content or ""
                try:
                    parsed = schema.model_validate_json(_json_da_resposta(texto))
                except ValidationError as exc:
                    if tentativa >= 2:
                        raise LLMIndisponivel(f"{m}: resposta fora do esquema ({str(exc)[:160]})") from exc
                    mensagens += [{"role": "assistant", "content": texto},
                                  {"role": "user", "content": f"O JSON não validou: {str(exc)[:600]}. Corrija e devolva só o objeto JSON."}]
                    continue
                self._gravar_cache(chave, {"parsed": parsed.model_dump(mode="json")})
                return parsed
            raise LLMIndisponivel(f"{m}: não foi possível obter JSON válido")

        with self._chamada("extrair", modelo, prompt) as reg:
            parsed = self._com_reserva(modelo, _run)[0]
            reg.saida_resumo = resumir(parsed.model_dump_json())
            return parsed

    def texto(self, modelo: str, system: str, prompt: str, max_tokens: int = 4000) -> str:
        def _run(m: str) -> str:
            payload = {"op": "texto", "provedor": "groq", "modelo": m, "system": system, "prompt": prompt}
            chave = self._chave(payload)
            cache = self._ler_cache(chave, m)
            if cache is not None:
                return cache["texto"]
            resp = self._criar(m, messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                               temperature=0, max_completion_tokens=max_tokens)
            texto = _RE_THINK.sub("", resp.choices[0].message.content or "").strip()
            self._gravar_cache(chave, {"texto": texto})
            return texto

        with self._chamada("texto", modelo, prompt) as reg:
            texto = self._com_reserva(modelo, _run)[0]
            reg.saida_resumo = resumir(texto)
            return texto

    def conversa(self, modelo: str, system: str, tools: list[dict[str, Any]]) -> Conversa:
        return _ConversaGroq(self, modelo, system, tools)


class _ConversaGroq(Conversa):
    def __init__(self, cliente: GroqClient, modelo: str, system: str, tools: list[dict[str, Any]]):
        self.c = cliente
        self.modelo = modelo
        self.tools = _tools_openai(tools)
        self.mensagens: list[dict[str, Any]] = [{"role": "system", "content": system}]
        self._ultima_entrada = ""

    def _rodada(self) -> RespostaLLM:
        with self.c._chamada("conversa", self.modelo, self._ultima_entrada) as reg:
            resposta = self._rodada_sem_trilha()
            reg.saida_resumo = _resumo_resposta(resposta)
            return resposta

    def _rodada_sem_trilha(self) -> RespostaLLM:
        import groq

        payload = {"op": "conversa", "provedor": "groq", "modelo": self.modelo, "mensagens": self.mensagens, "tools": self.tools}
        chave = self.c._chave(payload)
        dados = self.c._ler_cache(chave, self.modelo)
        if dados is None:
            def _run(m: str) -> dict[str, Any]:
                for tentativa in range(2):
                    try:
                        resp = self.c._criar(m, messages=self.mensagens, tools=self.tools, tool_choice="auto", temperature=0, max_completion_tokens=4000)
                    except groq.BadRequestError as exc:
                        codigo = _codigo_erro_groq(exc)
                        if "tool_use_failed" in codigo and tentativa == 0:
                            continue  # chamada de ferramenta malformada: uma nova tentativa costuma resolver
                        raise LLMIndisponivel(f"{m}: Groq recusou a rodada ({codigo[:160]})") from exc
                    escolha = resp.choices[0]
                    msg = escolha.message
                    return {
                        "content": _RE_THINK.sub("", msg.content or "").strip(),
                        "tool_calls": [{"id": t.id, "name": t.function.name, "arguments": t.function.arguments or "{}"} for t in (msg.tool_calls or [])],
                        "finish": escolha.finish_reason,
                    }
                raise LLMIndisponivel(f"{m}: chamadas de ferramenta malformadas")

            dados, _ = self.c._com_reserva(self.modelo, _run)
            self.c._gravar_cache(chave, dados)
        mensagem: dict[str, Any] = {"role": "assistant", "content": dados["content"] or None}
        if dados["tool_calls"]:
            mensagem["tool_calls"] = [{"id": t["id"], "type": "function", "function": {"name": t["name"], "arguments": t["arguments"]}} for t in dados["tool_calls"]]
        else:
            mensagem["content"] = dados["content"] or ""
        self.mensagens.append(mensagem)
        chamadas = []
        for t in dados["tool_calls"]:
            try:
                entrada = json.loads(t["arguments"]) if t["arguments"] else {}
            except json.JSONDecodeError:
                entrada = {}
            chamadas.append(ChamadaFerramenta(id=t["id"], nome=t["name"], entrada=entrada if isinstance(entrada, dict) else {}))
        parada = {"tool_calls": "ferramentas", "length": "limite", "content_filter": "recusa"}.get(dados.get("finish") or "", "fim")
        if chamadas:
            parada = "ferramentas"
        return RespostaLLM(texto=dados["content"], chamadas=chamadas, parada=parada)

    def enviar(self, texto: str) -> RespostaLLM:
        self.mensagens.append({"role": "user", "content": texto})
        self._ultima_entrada = texto
        return self._rodada()

    def responder_ferramentas(self, resultados: list[tuple[str, str, bool]]) -> RespostaLLM:
        for cid, saida, _erro in resultados:
            self.mensagens.append({"role": "tool", "tool_call_id": cid, "content": saida})
        self._ultima_entrada = _resumo_resultados(resultados)
        return self._rodada()


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


class AnthropicClient(LLMClient):
    provedor = "anthropic"

    def __init__(self, cfg: Config | None = None, uso: UsoLLM | None = None):
        super().__init__(cfg, uso)
        import anthropic

        self._client = anthropic.Anthropic(api_key=self.cfg.anthropic_api_key, max_retries=3)

    @property
    def disponivel(self) -> bool:
        return bool(self.cfg.anthropic_api_key)

    def _contabilizar_resposta(self, modelo: str, usage: Any) -> None:
        # output_tokens já inclui o thinking; output_tokens_details.thinking_tokens, quando vem, permite separá-lo
        saida = int(getattr(usage, "output_tokens", 0) or 0)
        detalhes = getattr(usage, "output_tokens_details", None)
        raciocinio = int(getattr(detalhes, "thinking_tokens", 0) or 0) if detalhes is not None else 0
        self._contabilizar(
            modelo,
            int(getattr(usage, "input_tokens", 0) or 0),
            max(saida - raciocinio, 0),
            cache_leitura=int(getattr(usage, "cache_read_input_tokens", 0) or 0),
            cache_escrita=int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
            raciocinio=raciocinio,
        )

    def extrair(self, modelo: str, system: str, prompt: str, schema: type[T], max_tokens: int = 8000) -> T:
        with self._chamada("extrair", modelo, prompt) as reg:
            parsed = self._extrair(modelo, system, prompt, schema, max_tokens)
            reg.saida_resumo = resumir(parsed.model_dump_json())
            return parsed

    def _extrair(self, modelo: str, system: str, prompt: str, schema: type[T], max_tokens: int) -> T:
        payload = {"op": "extrair", "provedor": "anthropic", "modelo": modelo, "system": system, "prompt": prompt, "schema": schema.model_json_schema()}
        chave = self._chave(payload)
        cache = self._ler_cache(chave, modelo)
        if cache is not None:
            return schema.model_validate(cache["parsed"])
        resposta = self._client.messages.parse(
            model=modelo,
            max_tokens=max_tokens,
            temperature=0,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
        self._contabilizar_resposta(modelo, resposta.usage)
        if resposta.stop_reason == "refusal":
            raise LLMIndisponivel(f"modelo recusou a requisição ({getattr(resposta.stop_details, 'category', None)})")
        parsed = resposta.parsed_output
        if parsed is None:
            raise LLMIndisponivel("resposta sem saída estruturada")
        self._gravar_cache(chave, {"parsed": parsed.model_dump(mode="json")})
        return parsed

    def _create(self, modelo: str, system: str, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None, max_tokens: int) -> Any:
        import anthropic

        payload = {"op": "conversar", "provedor": "anthropic", "modelo": modelo, "system": system, "messages": messages, "tools": tools}
        chave = self._chave(payload)
        cache = self._ler_cache(chave, modelo)
        if cache is not None:
            return anthropic.types.Message.model_validate(cache["message"])
        kwargs: dict[str, Any] = {"tools": tools} if tools else {}
        resposta = self._client.messages.create(
            model=modelo,
            max_tokens=max_tokens,
            temperature=0,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            **kwargs,
        )
        self._contabilizar_resposta(modelo, resposta.usage)
        self._gravar_cache(chave, {"message": resposta.model_dump(mode="json")})
        return resposta

    def texto(self, modelo: str, system: str, prompt: str, max_tokens: int = 4000) -> str:
        with self._chamada("texto", modelo, prompt) as reg:
            resposta = self._create(modelo, system, [{"role": "user", "content": prompt}], None, max_tokens)
            texto = "".join(b.text for b in resposta.content if getattr(b, "type", "") == "text").strip()
            reg.saida_resumo = resumir(texto)
            return texto

    def conversa(self, modelo: str, system: str, tools: list[dict[str, Any]]) -> Conversa:
        return _ConversaAnthropic(self, modelo, system, tools)


class _ConversaAnthropic(Conversa):
    def __init__(self, cliente: AnthropicClient, modelo: str, system: str, tools: list[dict[str, Any]]):
        self.c = cliente
        self.modelo = modelo
        self.system = system
        self.tools = tools
        self.messages: list[dict[str, Any]] = []
        self._ultima_entrada = ""

    def _rodada(self) -> RespostaLLM:
        with self.c._chamada("conversa", self.modelo, self._ultima_entrada) as reg:
            resposta = self.c._create(self.modelo, self.system, self.messages, self.tools, 8000)
            self.messages.append({"role": "assistant", "content": resposta.content})
            chamadas = [
                ChamadaFerramenta(id=b.id, nome=b.name, entrada=dict(b.input) if isinstance(b.input, dict) else json.loads(json.dumps(b.input)))
                for b in resposta.content
                if getattr(b, "type", "") == "tool_use"
            ]
            texto = " ".join(getattr(b, "text", "") for b in resposta.content if getattr(b, "type", "") == "text").strip()
            parada = {"refusal": "recusa", "max_tokens": "limite", "tool_use": "ferramentas"}.get(resposta.stop_reason or "", "fim")
            saida = RespostaLLM(texto=texto, chamadas=chamadas, parada=parada)
            reg.saida_resumo = _resumo_resposta(saida)
            return saida

    def enviar(self, texto: str) -> RespostaLLM:
        self.messages.append({"role": "user", "content": texto})
        self._ultima_entrada = texto
        return self._rodada()

    def responder_ferramentas(self, resultados: list[tuple[str, str, bool]]) -> RespostaLLM:
        self.messages.append(
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": cid, "content": saida, "is_error": erro} for cid, saida, erro in resultados]}
        )
        self._ultima_entrada = _resumo_resultados(resultados)
        return self._rodada()


# ---------------------------------------------------------------------------
# Fábrica
# ---------------------------------------------------------------------------


def criar_llm_client(cfg: Config | None = None, uso: UsoLLM | None = None) -> LLMClient:
    cfg = cfg or config
    if cfg.llm_provider == "gemini" and cfg.gemini_api_key:
        return GeminiClient(cfg, uso)
    if cfg.llm_provider == "groq" and cfg.groq_api_key:
        return GroqClient(cfg, uso)
    if cfg.llm_provider == "anthropic" and cfg.anthropic_api_key:
        return AnthropicClient(cfg, uso)
    return ClienteNulo(cfg, uso)
