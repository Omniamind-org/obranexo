"""Custo de IA por análise (métrica interna): cálculo pelos tokens × tabela e endpoint /api/custos."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from obranexo.config import config
from obranexo.connectors.pncp import carregar_caso
from obranexo.custos import custo_do_uso, resumo_custos
from obranexo.llm.client import criar_llm_client
from obranexo.models import Analise, Prospeccao, UsoLLM

CASO = config.dir_casos / "goianira_pe038_2026"
CFG = replace(config, llm_provider=None, cambio_brl=5.0, meta_custo_analise_brl=1.0)


def _uso(modelo="gemini-3.8-flash", entrada=100_000, saida=20_000, custo=0.0, chamadas=10):
    return UsoLLM(chamadas=chamadas, tokens_entrada=entrada, tokens_saida=saida, custo_usd=custo,
                  por_modelo={modelo: {"chamadas": chamadas, "entrada": entrada, "saida": saida}} if chamadas else {})


def _analise(id_, uso, quando=datetime(2026, 10, 24, 10, 0)):
    contratacao, itens, _ = carregar_caso(CASO)
    return Analise(id=id_, empresa_id="demo", contratacao=contratacao, itens=itens, iniciada_em=quando, uso_llm=uso, status="concluida")


def test_contabilizacao_usa_o_preco_de_tabela():
    uso = UsoLLM()
    cli = criar_llm_client(CFG, uso)
    cli._contabilizar("gemini-3.8-flash", 100_000, 20_000)
    assert uso.custo_usd == pytest.approx((100_000 * 0.75 + 20_000 * 3.75) / 1e6)  # US$ 0,15


def test_faixa_de_preco_por_chamada_do_haiku():
    uso = UsoLLM()
    cli = criar_llm_client(CFG, uso)
    cli._contabilizar("claude-haiku-5-5", 50_000, 1_000)
    abaixo = uso.custo_usd
    cli._contabilizar("claude-haiku-5-5", 150_000, 1_000)
    assert abaixo == pytest.approx((50_000 * 0.10 + 1_000 * 0.50) / 1e6)
    assert uso.custo_usd - abaixo == pytest.approx((150_000 * 0.50 + 1_000 * 2.50) / 1e6)


def test_custo_registrado_tem_precedencia_e_registro_zerado_e_recalculado():
    assert custo_do_uso(_uso(custo=0.42), CFG)[:2] == (0.42, "registrado")
    usd, origem, faltam = custo_do_uso(_uso(custo=0.0), CFG)
    assert origem == "recalculado" and usd == pytest.approx(0.15) and faltam == []
    assert custo_do_uso(_uso(chamadas=0), CFG)[:2] == (0.0, "sem_ia")


def test_modelo_sem_preco_e_sinalizado():
    usd, origem, faltam = custo_do_uso(_uso(modelo="modelo-novo"), CFG)
    assert usd == 0.0 and faltam == ["modelo-novo"]


def test_resumo_estatisticas_meta_e_periodo():
    analises = [
        _analise("a1", _uso(custo=0.10)),                          # R$ 0,50: dentro da meta
        _analise("a2", _uso(custo=0.30)),                          # R$ 1,50: fora
        _analise("a3", _uso(chamadas=0)),                          # modo determinístico: não entra na média
        _analise("a4", _uso(custo=0.20), datetime(2026, 9, 1)),    # fora do período
    ]
    prosp = [Prospeccao(id="p1", empresa_id="demo", empresa_nome="Demo", iniciada_em=datetime(2026, 10, 24), uso_llm=_uso(custo=0.05))]
    r = resumo_custos(analises, prosp, CFG, desde=date(2026, 10, 1), ate=date(2026, 10, 31))

    assert r["analises"]["quantidade"] == 3 and r["analises"]["com_ia"] == 2 and r["analises"]["sem_ia"] == 1
    assert r["analises"]["custo_total"] == {"usd": 0.4, "brl": 2.0}
    assert r["analises"]["por_analise"]["media"]["usd"] == pytest.approx(0.2)
    assert r["analises"]["por_analise"]["maximo"]["usd"] == pytest.approx(0.3)
    assert r["meta"] == {"custo_por_analise_brl": 1.0, "analises_dentro": 1, "analises_com_ia": 2}
    assert r["prospeccoes"]["custo_total"]["usd"] == pytest.approx(0.05)
    assert r["custo_total"]["usd"] == pytest.approx(0.45)
    linha = next(x for x in r["analises_recentes"] if x["id"] == "a1")
    assert linha["custo_por_item"]["usd"] == pytest.approx(0.10 / 6, abs=1e-6) and linha["dentro_da_meta"] is True
    assert next(x for x in r["analises_recentes"] if x["id"] == "a3")["custo"]["usd"] == 0.0
    modelo = r["por_modelo"][0]
    assert modelo["modelo"] == "gemini-3.8-flash" and modelo["provedor"] == "gemini"
    assert modelo["preco_tabela_usd_por_milhao"] == {"entrada": 0.75, "saida": 3.75}


def test_resumo_vazio_nao_quebra():
    r = resumo_custos([], [], CFG)
    assert r["analises"]["quantidade"] == 0 and r["analises"]["por_analise"]["media"] is None and r["por_modelo"] == []


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "dir_analises", tmp_path / "analises")
    monkeypatch.setattr(config, "dir_dados", tmp_path)
    monkeypatch.setattr(config, "llm_provider", None)
    from obranexo.api import main

    with TestClient(main.app) as c:
        yield c


def test_endpoint_custos(client):
    from obranexo.storage import store

    store.salvar(_analise("api-1", _uso(custo=0.12)))
    r = client.get("/api/custos", params={"desde": "2026-10-24", "ate": "2026-10-24"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["analises"]["com_ia"] == 1 and corpo["analises_recentes"][0]["id"] == "api-1"
    assert "interna" in corpo["aviso"]
    assert client.get("/api/custos", params={"desde": "2026-10-25", "ate": "2026-10-24"}).status_code == 400
    assert client.get("/api/custos", params={"desde": "2026-11-01"}).json()["analises"]["quantidade"] == 0
