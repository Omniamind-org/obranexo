"""Licitações coletadas do PNCP são da empresa que as baixou; os casos de demonstração são de todas."""

from __future__ import annotations

import json
import shutil

import pytest
from fastapi.testclient import TestClient

from obranexo.config import config
from obranexo.connectors.pncp import PNCPClient, carregar_caso

DEMO = "goianira_pe038_2026"
COLETADO = "01291707000167_2026_75"
pytestmark = pytest.mark.skipif(not (config.dir_casos / DEMO / "contratacao.json").exists(), reason="caso congelado ausente")


class _PNCPCopia(PNCPClient):
    """Coleta sem rede: o "download" é a cópia do pacote congelado de Goianira para a pasta de destino."""

    def coletar_caso(self, cnpj, ano, seq, destino, max_mb=None, so_pdf=False):
        shutil.copytree(self.origem, destino)
        return carregar_caso(destino)


@pytest.fixture()
def app(monkeypatch, tmp_path):
    from obranexo.api import auth, main

    # data/casos de mentira: o caso de demonstração e uma licitação coletada antes da separação por empresa
    casos = tmp_path / "casos"
    shutil.copytree(config.dir_casos / DEMO, casos / DEMO)
    shutil.copytree(config.dir_casos / DEMO, casos / "11111111000111_2026_1")
    _PNCPCopia.origem = config.dir_casos / DEMO
    monkeypatch.setattr(config, "dir_casos", casos)
    monkeypatch.setattr(config, "offline", False)
    monkeypatch.setattr(config, "llm_provider", None)
    monkeypatch.setattr(main, "PNCPClient", _PNCPCopia)
    auth._erros.clear()
    main._estado.clear()
    yield main.app
    main._estado.clear()


def _analisar(c: TestClient, caso: str) -> str:
    r = c.post("/api/analises", json={"caso": caso})
    assert r.status_code == 202, r.text
    with c.stream("GET", f"/api/jobs/{r.json()['id']}/eventos") as stream:
        for linha in stream.iter_lines():
            if linha.startswith("data: ") and '"analise_id"' in linha:
                fim = json.loads(linha[6:])
                if fim.get("status") != "executando":
                    assert fim["status"] == "concluida", fim
                    return fim["analise_id"]
    raise AssertionError("o job não terminou")


def test_licitacao_coletada_so_aparece_para_quem_coletou(app, entrar, tmp_path):
    with TestClient(app) as a, TestClient(app) as b:
        ua = entrar(a, email="ana@alfa.com.br", empresa="Alfa")
        entrar(b, email="bia@beta.com.br", empresa="Beta")

        r = a.post("/api/pncp/coletar", json={"cnpj": "01291707000167", "ano": 2026, "sequencial": 75})
        assert r.status_code == 200, r.text
        assert (tmp_path / "empresas" / ua.empresa_id / "casos" / COLETADO / "contratacao.json").exists()
        assert not (config.dir_casos / COLETADO).exists()

        nomes_a = {x["nome"] for x in a.get("/api/casos").json()}
        nomes_b = {x["nome"] for x in b.get("/api/casos").json()}
        assert nomes_a == {DEMO, COLETADO}
        assert nomes_b == {DEMO}  # a demonstração é de todas; a coletada antes da separação, de nenhuma

        assert a.get(f"/api/casos/{COLETADO}").status_code == 200
        assert b.get(f"/api/casos/{COLETADO}").status_code == 404
        assert b.post("/api/analises", json={"caso": COLETADO}).status_code == 404
        for c in (a, b):
            assert c.get("/api/casos/11111111000111_2026_1").status_code == 404
            assert c.get("/api/casos/..%2F..%2Fempresas").status_code == 404


def test_prova_no_edital_funciona_com_a_licitacao_na_pasta_da_empresa(app, entrar):
    with TestClient(app) as a:
        entrar(a, email="ana@alfa.com.br", empresa="Alfa")
        assert a.post("/api/pncp/coletar", json={"cnpj": "01291707000167", "ano": 2026, "sequencial": 75}).status_code == 200
        analise_id = _analisar(a, COLETADO)
        analise = a.get(f"/api/analises/{analise_id}").json()["analise"]
        ev = next(e for e in analise["evidencias"] if not e["documento_id"].startswith("pncp-item"))
        r = a.get(f"/api/analises/{analise_id}/evidencias/{ev['id']}").json()
        assert r["documento"]["tem_arquivo"] and r["texto_pagina"]
        pdf = a.get(f"/api/analises/{analise_id}/documentos/{ev['documento_id']}/arquivo")
        assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_status_publico_conta_so_a_demonstracao(app, entrar):
    with TestClient(app) as a:
        entrar(a, email="ana@alfa.com.br", empresa="Alfa")
        a.post("/api/pncp/coletar", json={"cnpj": "01291707000167", "ano": 2026, "sequencial": 75})
    with TestClient(app) as anonimo:
        assert anonimo.get("/api/status").json()["casos"] == 1


def test_fora_da_api_tudo_continua_em_data_casos(app):
    from obranexo.storage import store

    assert store.dir_casos() == config.dir_casos
    assert {p.name for p in store.listar_casos()} == {DEMO, "11111111000111_2026_1"}


def test_prospector_grava_a_licitacao_na_pasta_da_empresa(app, tmp_path):
    from obranexo import contas
    from obranexo.agents.prospector import Prospector
    from obranexo.catalog.loader import carregar_catalogo_json
    from obranexo.config import Config

    empresa_id = contas.criar_empresa("Alfa")
    cfg = Config(llm_provider=None, gemini_api_key=None, anthropic_api_key=None, groq_api_key=None, dir_dados=tmp_path)
    with contas.na_empresa(empresa_id):
        pr = Prospector(carregar_catalogo_json(config.catalogo_demo), ["GO"], 30, 1, cfg=cfg)
        pr.pncp = _PNCPCopia(offline=True, pausa_s=0)
        assert not pr.analisar("01291707000167-1-000075/2026", "teste").startswith("ERRO"), pr.p.log[-1].mensagem
    assert (tmp_path / "empresas" / empresa_id / "casos" / COLETADO / "contratacao.json").exists()
    assert not (config.dir_casos / COLETADO).exists()
