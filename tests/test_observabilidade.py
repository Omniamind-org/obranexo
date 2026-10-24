"""Trilha de chamadas de modelo e custo real: escopo por agente, tokens de raciocínio, cache, reserva, erro e agregados."""

from __future__ import annotations

import contextvars
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from obranexo.config import Config, config
from obranexo.llm.client import AnthropicClient, GeminiClient, GroqClient, LLMClient, LLMIndisponivel
from obranexo.observability import trilha as mod
from obranexo.observability.trilha import ChamadaLLM, Trilha, agregar, escopo, escopo_atual


@pytest.fixture
def banco(tmp_path, monkeypatch):
    """Trilha num SQLite temporário, ligada ao cliente de LLM pelo singleton do módulo."""
    monkeypatch.setattr(config, "dir_dados", tmp_path)
    t = Trilha(tmp_path / "obranexo.db")
    monkeypatch.setattr(mod, "trilha", t)
    monkeypatch.setattr("obranexo.llm.client.trilha", t)
    return t


class _ClienteFalso(LLMClient):
    """Provedor de mentira: só exercita a base (trilha, cache, contabilização, reserva)."""

    provedor = "falso"

    def __init__(self, cfg: Config, respostas: dict[str, object]):
        super().__init__(cfg)
        self.respostas = respostas  # modelo -> texto ou exceção

    @property
    def disponivel(self) -> bool:
        return True

    def texto(self, modelo: str, system: str, prompt: str, max_tokens: int = 4000) -> str:
        def _run(m: str) -> str:
            chave = self._chave({"op": "texto", "provedor": self.provedor, "modelo": m, "system": system, "prompt": prompt})
            cache = self._ler_cache(chave, m)
            if cache is not None:
                return cache["texto"]
            r = self.respostas[m]
            if isinstance(r, Exception):
                raise r
            self._contabilizar(m, entrada=1000, saida=200, raciocinio=300)
            self._gravar_cache(chave, {"texto": r})
            return str(r)

        with self._chamada("texto", modelo, prompt) as reg:
            saida = self._com_reserva(modelo, _run)[0]
            reg.saida_resumo = saida
            return saida

    def extrair(self, *a, **k):  # pragma: no cover - não usado aqui
        raise NotImplementedError

    def conversa(self, *a, **k):  # pragma: no cover - não usado aqui
        raise NotImplementedError


def _cfg(tmp_path) -> Config:
    return Config(
        llm_provider=None, gemini_api_key=None, groq_api_key=None, anthropic_api_key=None, dir_llm_cache=tmp_path / "cache", llm_cache=True,
        precos_usd={"principal": (1.0, 10.0, 0.1), "reserva": (0.5, 5.0, 0.05)}, modelos_reserva=["reserva"],
    )


# ----------------------------------------------------------------------------- escopo


def test_escopo_aninha_herda_e_restaura():
    assert escopo_atual().agente == "sistema"
    with escopo(origem_tipo="analise", origem_id="A1"):
        with escopo(agente="investigador", versao_prompt="v9"):
            e = escopo_atual()
            assert (e.agente, e.origem_id, e.versao_prompt) == ("investigador", "A1", "v9")
        assert escopo_atual().agente == "sistema" and escopo_atual().origem_id == "A1"
    assert escopo_atual().origem_id is None


def test_escopo_chega_nas_threads_do_lote():
    """Threads novas não herdam contextvars: a cópia precisa ser feita na thread de origem, uma por tarefa (como em extrator.py)."""
    with escopo(agente="analista_tecnico", origem_id="A2"):
        copias = [contextvars.copy_context() for _ in range(3)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            vistos = list(pool.map(lambda c: c.run(lambda: escopo_atual().agente), copias))
            sem_copia = list(pool.map(lambda _: escopo_atual().agente, range(2)))
    assert vistos == ["analista_tecnico"] * 3
    assert sem_copia == ["sistema", "sistema"]


# ----------------------------------------------------------------------------- trilha via cliente


def test_chamada_grava_tokens_custo_latencia_e_agente(banco, tmp_path):
    cli = _ClienteFalso(_cfg(tmp_path), {"principal": "ok"})
    with escopo(agente="verificador", versao_prompt="v0.4", origem_tipo="analise", origem_id="AN-1"):
        assert cli.texto("principal", "sistema", "pergunta") == "ok"
    linhas = banco.listar("AN-1")
    assert len(linhas) == 1
    c = linhas[0]
    assert c["agente"] == "verificador" and c["versao_prompt"] == "v0.4" and c["operacao"] == "texto"
    assert c["modelo_pedido"] == "principal" and c["modelo_usado"] == "principal" and not c["reserva"]
    assert (c["tokens_entrada"], c["tokens_saida"], c["tokens_raciocinio"]) == (1000, 200, 300)
    # 1000 × 1,0 + (200 + 300) × 10,0 por milhão: o raciocínio é cobrado como saída
    assert c["custo_usd"] == pytest.approx(0.006)
    assert c["status"] == "ok" and c["latencia_ms"] >= 0 and c["entrada_resumo"] == "pergunta" and c["saida_resumo"] == "ok"
    assert cli.uso.tokens_raciocinio == 300 and cli.uso.custo_usd == pytest.approx(0.006) and cli.uso.chamadas == 1


def test_cache_hit_vira_linha_sem_custo(banco, tmp_path):
    cfg = _cfg(tmp_path)
    with escopo(origem_id="AN-2"):
        _ClienteFalso(cfg, {"principal": "ok"}).texto("principal", "s", "p")
        cli2 = _ClienteFalso(cfg, {"principal": "ok"})
        cli2.texto("principal", "s", "p")
    linhas = banco.listar("AN-2")
    assert [c["cache_hit"] for c in linhas] == [False, True]
    assert linhas[1]["custo_usd"] == 0 and linhas[1]["tokens_entrada"] == 0 and linhas[1]["modelo_usado"] == "principal"
    assert cli2.uso.chamadas == 0 and cli2.uso.chamadas_cache == 1


def test_reserva_fica_registrada(banco, tmp_path):
    cli = _ClienteFalso(_cfg(tmp_path), {"principal": LLMIndisponivel("429"), "reserva": "veio do reserva"})
    LLMClient._indisponiveis.clear()
    with escopo(origem_id="AN-3"):
        assert cli.texto("principal", "s", "p") == "veio do reserva"
    c = banco.listar("AN-3")[0]
    assert c["modelo_pedido"] == "principal" and c["modelo_usado"] == "reserva" and c["reserva"] is True and c["status"] == "ok"
    assert cli.uso.chamadas_reserva == 1
    LLMClient._indisponiveis.clear()


def test_erro_tambem_vira_linha(banco, tmp_path):
    cli = _ClienteFalso(_cfg(tmp_path), {"principal": LLMIndisponivel("sem cota"), "reserva": LLMIndisponivel("fora")})
    LLMClient._indisponiveis.clear()
    with escopo(origem_id="AN-4"), pytest.raises(LLMIndisponivel):
        cli.texto("principal", "s", "p")
    c = banco.listar("AN-4")[0]
    assert c["status"] == "erro" and "LLMIndisponivel" in c["erro"] and c["custo_usd"] == 0
    LLMClient._indisponiveis.clear()


# ----------------------------------------------------------------------------- tokens de raciocínio por provedor


def _cliente_sem_sdk(classe, cfg):
    cli = classe.__new__(classe)
    LLMClient.__init__(cli, cfg)
    return cli


def test_gemini_separa_thinking_da_resposta(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.precos_usd["g"] = (1.0, 10.0, 0.1)
    cli = _cliente_sem_sdk(GeminiClient, cfg)
    resposta = SimpleNamespace(usage_metadata=SimpleNamespace(prompt_token_count=1200, candidates_token_count=100, thoughts_token_count=400, cached_content_token_count=200))
    cli._contabilizar_resposta("g", resposta)
    assert (cli.uso.tokens_entrada, cli.uso.tokens_saida, cli.uso.tokens_raciocinio, cli.uso.tokens_cache_leitura) == (1000, 100, 400, 200)
    # 1000 × 1,0 + 200 × 0,1 (cache) + 500 × 10,0 por milhão
    assert cli.uso.custo_usd == pytest.approx(0.00602)


def test_groq_le_reasoning_tokens_dentro_de_completion(tmp_path):
    cli = _cliente_sem_sdk(GroqClient, _cfg(tmp_path))
    cli._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **k: SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=50, completion_tokens=80, completion_tokens_details=SimpleNamespace(reasoning_tokens=60))))))
    cli._criar("openai/gpt-oss-20b", messages=[])
    assert (cli.uso.tokens_entrada, cli.uso.tokens_saida, cli.uso.tokens_raciocinio) == (50, 20, 60)


def test_anthropic_le_thinking_tokens_dentro_de_output(tmp_path):
    cli = _cliente_sem_sdk(AnthropicClient, _cfg(tmp_path))
    cli._contabilizar_resposta("claude-haiku-5-5", SimpleNamespace(input_tokens=10, output_tokens=30, output_tokens_details=SimpleNamespace(thinking_tokens=25),
                                                               cache_read_input_tokens=0, cache_creation_input_tokens=0))
    assert (cli.uso.tokens_saida, cli.uso.tokens_raciocinio) == (5, 25)


# ----------------------------------------------------------------------------- agregados


def _linha(**kw) -> dict:
    base = ChamadaLLM.nova("texto", "gemini", "m")
    base.modelo_usado = "m"
    d = base.__dict__ | kw
    return d


def test_agregar_calcula_taxas_p95_e_quebras():
    linhas = [
        _linha(agente="a", latencia_ms=100, custo_usd=0.01, tokens_raciocinio=5),
        _linha(agente="a", latencia_ms=900, custo_usd=0.02),
        _linha(agente="b", latencia_ms=0, cache_hit=True),
        _linha(agente="b", latencia_ms=300, status="erro", reserva=True),
    ]
    r = agregar(linhas)
    assert r["chamadas"] == 4 and r["chamadas_api"] == 3 and r["custo_usd"] == pytest.approx(0.03)
    assert r["latencia_ms"]["p95"] == 900 and r["latencia_ms"]["media"] == 433
    assert r["taxa_cache"] == 0.25 and r["taxa_reserva"] == 0.25 and r["taxa_erro"] == 0.25
    assert r["tokens"]["raciocinio"] == 5
    por_agente = {g["agente"]: g for g in r["por_agente"]}
    assert por_agente["a"]["chamadas"] == 2 and por_agente["b"]["cache_hits"] == 1 and por_agente["b"]["erros"] == 1
    assert r["por_agente"][0]["agente"] == "a"  # ordenado por custo


def test_agregar_vazio():
    r = agregar([])
    assert r["chamadas"] == 0 and r["latencia_ms"]["p95"] == 0 and r["por_agente"] == []
