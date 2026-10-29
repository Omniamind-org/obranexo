"""Testes da API HTTP e do servimento do frontend (sem LLM, sobre os casos congelados)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from obranexo.config import config

CASO = "goianira_pe038_2026"
pytestmark = pytest.mark.skipif(not (config.dir_casos / CASO / "contratacao.json").exists(), reason="caso congelado ausente")


@pytest.fixture()
def client(tmp_path, monkeypatch, entrar):
    monkeypatch.setattr(config, "dir_analises", tmp_path / "analises")
    monkeypatch.setattr(config, "dir_dados", tmp_path)  # catálogo ativo e prospecções num diretório temporário
    monkeypatch.setattr(config, "llm_provider", None)  # rápido e sem cota
    from obranexo.api import main

    main._estado.clear()
    with TestClient(main.app) as c:
        c.usuario = entrar(c)
        yield c
    main._estado.clear()


def _executar(client: TestClient, caso: str = CASO) -> str:
    r = client.post("/api/analises", json={"caso": caso})
    assert r.status_code == 202, r.text
    job_id = r.json()["id"]
    eventos, fim = [], None
    with client.stream("GET", f"/api/jobs/{job_id}/eventos") as stream:
        tipo = None
        for linha in stream.iter_lines():
            if linha.startswith("event: "):
                tipo = linha[7:]
            elif linha.startswith("data: "):
                dados = json.loads(linha[6:])
                if tipo == "log":
                    eventos.append(dados)
                elif tipo == "fim":
                    fim = dados
                    break
    assert fim and fim["status"] == "concluida", fim
    nos = {e["no"] for e in eventos}
    assert {"carregar_contexto", "extrair_itens", "casar_com_catalogo", "verificador", "gerar_dossie"} <= nos
    return fim["analise_id"]


def test_frontend_e_status(client):
    r = client.get("/")
    assert r.status_code == 200 and '<script type="module" src="/js/app.js">' in r.text
    assert client.get("/js/app.js").status_code == 200
    assert client.get("/css/app.css").status_code == 200
    s = client.get("/api/status").json()
    assert s["llm"]["disponivel"] is False and s["casos"] >= 1
    assert client.get("/api/docs").status_code == 200


def test_catalogo_e_casos(client):
    cat = client.get("/api/catalogo").json()
    assert len(cat["produtos"]) > 10 and "luminaria_publica_led" in cat["categorias"]
    casos = client.get("/api/casos").json()
    assert any(c["nome"] == CASO for c in casos)
    det = client.get(f"/api/casos/{CASO}").json()
    assert len(det["itens"]) == 6 and det["contratacao"]["uf"] == "GO"
    assert client.get("/api/casos/..%2F..%2Fsrc").status_code == 404
    assert client.post("/api/analises", json={"caso": "nao_existe"}).status_code == 404


def test_upload_catalogo_csv(client):
    csv = "sku,nome,categoria,potencia_w,ip\nX-1,Luminária teste,luminaria_publica_led,100,IP66\n"
    r = client.post("/api/catalogo", files={"arquivo": ("cat.csv", csv.encode(), "text/csv")})
    assert r.status_code == 200 and r.json()["produtos"] == 1
    assert client.get("/api/catalogo").json()["produtos"][0]["sku"] == "X-1"
    assert client.post("/api/catalogo", files={"arquivo": ("x.txt", b"oi", "text/plain")}).status_code == 400
    assert client.delete("/api/catalogo").json()["produtos"] > 10


def test_catalogo_editavel_e_persistido(client, tmp_path):
    from obranexo.api import main

    produto = {"id": "NOVO-1", "sku": "NOVO-1", "nome": "Luminária importada", "categoria": "luminaria_publica_led",
               "atributos": {"potencia_w": {"valor": 120, "unidade": "W", "tipo": "numero"}}}
    r = client.post("/api/catalogo/produtos", json={"produtos": [produto]})
    assert r.status_code == 200 and r.json()["adicionados"] == 1
    salvo = tmp_path / "empresas" / client.usuario.empresa_id / "catalogo_ativo.json"
    assert salvo.exists()
    main._estado.clear()  # simula reinício do servidor: recarrega do disco
    skus = [p["sku"] for p in client.get("/api/catalogo").json()["produtos"]]
    assert "NOVO-1" in skus
    assert client.delete("/api/catalogo/produtos/NOVO-1").status_code == 200
    assert client.delete("/api/catalogo/produtos/NOVO-1").status_code == 404
    client.delete("/api/catalogo")
    assert not salvo.exists()


def test_funcoes_de_ia_exigem_llm(client):
    assert client.post("/api/catalogo/importar", data={"texto": "x" * 100}).status_code == 409
    assert client.post("/api/prospeccoes", json={"ufs": ["GO"]}).status_code == 409
    assert client.get("/api/prospeccoes").json() == []


def test_fluxo_completo_de_analise(client):
    analise_id = _executar(client)

    det = client.get(f"/api/analises/{analise_id}").json()
    assert det["resumo"]["caso"] == CASO
    assert det["resumo"]["resultados"]["COMPATIVEL"] == 4 and det["resumo"]["resultados"]["PARCIAL"] == 2
    assert det["resumo"]["evidencias_verificadas"] == det["resumo"]["evidencias_total"]
    assert det["produtos"] and det["atributos"]["potencia_w"]["rotulo"] == "Potência"

    lista = client.get("/api/analises").json()
    assert lista[0]["id"] == analise_id

    md = client.get(f"/api/analises/{analise_id}/dossie.md")
    assert md.status_code == 200 and md.text.startswith("# Dossiê comercial")
    assert "attachment" in client.get(f"/api/analises/{analise_id}/dossie.md?download=true").headers["content-disposition"]

    # Evidência vinda do edital (página de PDF) e arquivo original
    analise = det["analise"]
    ev = next(e for e in analise["evidencias"] if not e["documento_id"].startswith("pncp-item"))
    r = client.get(f"/api/analises/{analise_id}/evidencias/{ev['id']}").json()
    assert r["documento"]["tem_arquivo"] and r["texto_pagina"]
    pdf = client.get(f"/api/analises/{analise_id}/documentos/{ev['documento_id']}/arquivo")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf" and pdf.content[:4] == b"%PDF"
    # Evidência de descrição de item
    ev_item = next(e for e in analise["evidencias"] if e["documento_id"].startswith("pncp-item"))
    r = client.get(f"/api/analises/{analise_id}/evidencias/{ev_item['id']}").json()
    assert ev_item["trecho_literal"] in r["texto_pagina"]

    rev = client.patch(f"/api/analises/{analise_id}/revisao", json={"status": "APROVADO", "comentario": "seguir"})
    assert rev.status_code == 200 and rev.json()["revisao"] == "APROVADO"
    assert client.get(f"/api/analises/{analise_id}").json()["resumo"]["revisao"] == "APROVADO"

    m = client.get("/api/metricas").json()
    assert m["concluidas"] == 1 and m["rastreabilidade"] == 1.0 and m["revisoes"]["APROVADO"] == 1

    assert client.get("/api/conteudo/fluxo").text.startswith("# Fluxo dos agentes")
    assert client.get("/api/analises/nao-existe").status_code == 404
