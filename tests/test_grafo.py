"""O grafo da análise como dado: declaração coerente, execução condicional e exposição pela API."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from obranexo.agents.grafo import Grafo, No
from obranexo.agents.pipeline import GRAFO
from obranexo.config import config


def test_grafo_declarado_e_coerente():
    nomes = [n.nome for n in GRAFO.nos]
    assert len(nomes) == len(set(nomes)) and nomes[0] == "carregar_contexto" and nomes[-1] == "gerar_dossie"
    for no in GRAFO.nos:
        assert no.le and no.escreve, no.nome
        assert (no.agente is None) == (no.modelo is None), f"{no.nome}: agente e modelo andam juntos"
        assert (no.condicao is None) == (no.quando is None), f"{no.nome}: condição em palavras e em código andam juntas"
    agentes = {n.agente for n in GRAFO.nos if n.agente}
    assert agentes == {"analista_tecnico", "especificador", "investigador", "verificador", "planejador"}
    assert all(c in GRAFO.estado["campos"] for c in ("analise.requisitos", "analise.correspondencias", "relevantes"))


def test_descricao_serializa_e_mermaid_cobre_todos_os_nos():
    d = GRAFO.descrever()
    json.dumps(d)
    assert [n["ordem"] for n in d["nos"]] == list(range(1, len(GRAFO.nos) + 1))
    for no in GRAFO.nos:
        assert no.nome in d["mermaid"] and f"`{no.nome}`" in GRAFO.markdown()
    assert "|regras|" not in d["mermaid"] and "classDef llm" in d["mermaid"]


def test_no_condicional_e_pulado_com_evento():
    class _Ctx:
        def __init__(self):
            self.rodou = []
            self.eventos = []

        def evento(self, no, mensagem, **_):
            self.eventos.append((no, mensagem))

    g = Grafo(
        estado={"descricao": "", "campos": []},
        nos=(
            No("a", "A", "", lambda c: c.rodou.append("a"), "x"),
            No("b", "B", "", lambda c: c.rodou.append("b"), "x", condicao="nunca", quando=lambda c: False),
            No("c", "C", "", lambda c: c.rodou.append("c"), "x", condicao="sempre", quando=lambda c: True),
        ),
    )
    ctx = _Ctx()
    g.executar(ctx)
    assert ctx.rodou == ["a", "c"]
    assert ctx.eventos == [("b", "Etapa não se aplica (nunca)")]


def test_nomes_repetidos_sao_recusados():
    with pytest.raises(ValueError):
        Grafo(estado={}, nos=(No("a", "A", "", lambda c: None, "x"), No("a", "A2", "", lambda c: None, "x")))


@pytest.fixture
def client(tmp_path, monkeypatch, entrar):
    monkeypatch.setattr(config, "dir_analises", tmp_path / "analises")
    monkeypatch.setattr(config, "dir_dados", tmp_path)  # a trilha (obranexo.db) também vai para o diretório temporário
    monkeypatch.setattr(config, "llm_provider", None)
    from obranexo.api.main import app

    with TestClient(app) as c:
        c.usuario = entrar(c, admin=True)  # /api/metricas/llm é só para administradores
        yield c


def test_api_expoe_grafo_trilha_e_metricas_de_llm(client):
    grafo = client.get("/api/conteudo/grafo").json()
    assert [n["nome"] for n in grafo["nos"]] == [n.nome for n in GRAFO.nos] and grafo["estado"]["campos"]

    assert client.get("/api/status").json()["versao_prompt"]
    assert client.get("/api/analises/nao-existe/chamadas").status_code == 404

    from obranexo import contas
    from obranexo.agents.pipeline import executar_caso
    from obranexo.catalog.loader import carregar_catalogo_json

    with contas.na_empresa(client.usuario.empresa_id):  # gravada na empresa logada, como faria a API
        analise = executar_caso(config.dir_casos / "goianira_pe038_2026", carregar_catalogo_json(config.catalogo_demo))
    assert analise.status == "concluida" and analise.versao_prompts
    pulados = [ev.mensagem for ev in analise.log if ev.mensagem.startswith("Etapa não se aplica")]
    assert pulados, "sem LLM o Especificador não roda e isso fica na trilha"

    trilha = client.get(f"/api/analises/{analise.id}/chamadas").json()
    assert trilha["chamadas"] == [] and trilha["resumo"]["chamadas"] == 0  # modo determinístico: nenhuma chamada de modelo

    m = client.get("/api/metricas/llm").json()
    assert m["chamadas"] == 0 and "precos_usd" in m and m["nota"]
