"""Clientes de modelos de linguagem com interface única para o restante do sistema.

Provedores: Google Gemini (SDK `google-genai`) e Anthropic (SDK `anthropic`).
Toda chamada passa por aqui para que:
  - custo e tokens de cada análise sejam contabilizados (UsoLLM);
  - respostas idênticas sejam reaproveitadas do cache em disco (reprodutibilidade);
  - falhas transitórias (429/503) tenham retentativa e, se persistirem, caiam para um modelo reserva;
  - os agentes dependam só de três operações: extrair (saída estruturada), texto e conversa (ferramentas).
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from obranexo.config import Config, config
from obranexo.models import UsoLLM

T = TypeVar("T", bound=BaseModel)


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
        self.cfg.dir_llm_cache.mkdir(parents=True, exist_ok=True)

    @property
    def disponivel(self) -> bool:
        return False

    def excedeu_orcamento(self) -> bool:
        return (self.uso.tokens_entrada + self.uso.tokens_saida) > self.cfg.orcamento_tokens

    # ------------------------------------------------------------ cache

    def _chave(self, payload: dict[str, Any]) -> Path:
        bruto = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()
        return self.cfg.dir_llm_cache / f"{hashlib.sha256(bruto).hexdigest()}.json"

    def _ler_cache(self, chave: Path) -> dict[str, Any] | None:
        if self.cfg.llm_cache and chave.exists():
            return json.loads(chave.read_text(encoding="utf-8"))
        return None

    def _gravar_cache(self, chave: Path, dados: dict[str, Any]) -> None:
        if self.cfg.llm_cache:
            chave.write_text(json.dumps(dados, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    # ------------------------------------------------------------ custo

    def _contabilizar(self, modelo: str, entrada: int, saida: int, cache_leitura: int = 0, cache_escrita: int = 0) -> None:
        preco_in, preco_out = self.cfg.precos_usd.get(modelo, (0.0, 0.0))
        custo = (entrada * preco_in + cache_escrita * preco_in * 1.25 + cache_leitura * preco_in * 0.1 + saida * preco_out) / 1_000_000
        self.uso.chamadas += 1
        self.uso.tokens_entrada += entrada + cache_escrita
        self.uso.tokens_saida += saida
        self.uso.tokens_cache_leitura += cache_leitura
        self.uso.custo_usd = round(self.uso.custo_usd + custo, 6)
        pm = self.uso.por_modelo.setdefault(modelo, {"chamadas": 0, "entrada": 0, "saida": 0})
        pm["chamadas"] += 1
        pm["entrada"] += entrada + cache_escrita + cache_leitura
        pm["saida"] += saida

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

        cfg = types.GenerateContentConfig(**config_extra)
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
        saida = int(getattr(um, "candidates_token_count", 0) or 0) + int(getattr(um, "thoughts_token_count", 0) or 0)
        cache = int(getattr(um, "cached_content_token_count", 0) or 0)
        self._contabilizar(modelo, entrada - cache, saida, cache_leitura=cache)

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
            cache = self._ler_cache(chave)
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

        return self._com_reserva(modelo, _run)[0]

    def texto(self, modelo: str, system: str, prompt: str, max_tokens: int = 4000) -> str:
        def _run(m: str) -> str:
            payload = {"op": "texto", "provedor": "gemini", "modelo": m, "system": system, "prompt": prompt}
            chave = self._chave(payload)
            cache = self._ler_cache(chave)
            if cache is not None:
                return cache["texto"]
            resposta = self._gerar(m, prompt, {"system_instruction": system, "max_output_tokens": max_tokens})
            self._contabilizar_resposta(m, resposta)
            texto = (getattr(resposta, "text", None) or "").strip()
            self._gravar_cache(chave, {"texto": texto})
            return texto

        return self._com_reserva(modelo, _run)[0]

    def conversa(self, modelo: str, system: str, tools: list[dict[str, Any]]) -> Conversa:
        return _ConversaGemini(self, modelo, system, tools)


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

    def _rodada(self) -> RespostaLLM:
        from google.genai import types

        payload = {"op": "conversa", "provedor": "gemini", "modelo": self.modelo, "system": self.system,
                   "historico": [h.model_dump(mode="json", exclude_none=True) for h in self.historico]}
        chave = self.c._chave(payload)
        cache = self.c._ler_cache(chave)
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
        return self._rodada()

    def responder_ferramentas(self, resultados: list[tuple[str, str, bool]]) -> RespostaLLM:
        from google.genai import types

        partes = [
            types.Part.from_function_response(name=self._nomes.get(cid, cid), response={"erro": saida} if erro else {"resultado": saida})
            for cid, saida, erro in resultados
        ]
        self.historico.append(types.Content(role="user", parts=partes))
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
        self._contabilizar(
            modelo,
            int(getattr(usage, "input_tokens", 0) or 0),
            int(getattr(usage, "output_tokens", 0) or 0),
            cache_leitura=int(getattr(usage, "cache_read_input_tokens", 0) or 0),
            cache_escrita=int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
        )

    def extrair(self, modelo: str, system: str, prompt: str, schema: type[T], max_tokens: int = 8000) -> T:
        payload = {"op": "extrair", "provedor": "anthropic", "modelo": modelo, "system": system, "prompt": prompt, "schema": schema.model_json_schema()}
        chave = self._chave(payload)
        cache = self._ler_cache(chave)
        if cache is not None:
            return schema.model_validate(cache["parsed"])
        resposta = self._client.messages.parse(
            model=modelo,
            max_tokens=max_tokens,
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
        cache = self._ler_cache(chave)
        if cache is not None:
            return anthropic.types.Message.model_validate(cache["message"])
        kwargs: dict[str, Any] = {"tools": tools} if tools else {}
        resposta = self._client.messages.create(
            model=modelo,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
            **kwargs,
        )
        self._contabilizar_resposta(modelo, resposta.usage)
        self._gravar_cache(chave, {"message": resposta.model_dump(mode="json")})
        return resposta

    def texto(self, modelo: str, system: str, prompt: str, max_tokens: int = 4000) -> str:
        resposta = self._create(modelo, system, [{"role": "user", "content": prompt}], None, max_tokens)
        return "".join(b.text for b in resposta.content if getattr(b, "type", "") == "text").strip()

    def conversa(self, modelo: str, system: str, tools: list[dict[str, Any]]) -> Conversa:
        return _ConversaAnthropic(self, modelo, system, tools)


class _ConversaAnthropic(Conversa):
    def __init__(self, cliente: AnthropicClient, modelo: str, system: str, tools: list[dict[str, Any]]):
        self.c = cliente
        self.modelo = modelo
        self.system = system
        self.tools = tools
        self.messages: list[dict[str, Any]] = []

    def _rodada(self) -> RespostaLLM:
        resposta = self.c._create(self.modelo, self.system, self.messages, self.tools, 8000)
        self.messages.append({"role": "assistant", "content": resposta.content})
        chamadas = [
            ChamadaFerramenta(id=b.id, nome=b.name, entrada=dict(b.input) if isinstance(b.input, dict) else json.loads(json.dumps(b.input)))
            for b in resposta.content
            if getattr(b, "type", "") == "tool_use"
        ]
        texto = " ".join(getattr(b, "text", "") for b in resposta.content if getattr(b, "type", "") == "text").strip()
        parada = {"refusal": "recusa", "max_tokens": "limite", "tool_use": "ferramentas"}.get(resposta.stop_reason or "", "fim")
        return RespostaLLM(texto=texto, chamadas=chamadas, parada=parada)

    def enviar(self, texto: str) -> RespostaLLM:
        self.messages.append({"role": "user", "content": texto})
        return self._rodada()

    def responder_ferramentas(self, resultados: list[tuple[str, str, bool]]) -> RespostaLLM:
        self.messages.append(
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": cid, "content": saida, "is_error": erro} for cid, saida, erro in resultados]}
        )
        return self._rodada()


# ---------------------------------------------------------------------------
# Fábrica
# ---------------------------------------------------------------------------


def criar_llm_client(cfg: Config | None = None, uso: UsoLLM | None = None) -> LLMClient:
    cfg = cfg or config
    if cfg.llm_provider == "gemini" and cfg.gemini_api_key:
        return GeminiClient(cfg, uso)
    if cfg.llm_provider == "anthropic" and cfg.anthropic_api_key:
        return AnthropicClient(cfg, uso)
    return ClienteNulo(cfg, uso)
