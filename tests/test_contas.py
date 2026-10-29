"""Login e isolamento por empresa: sem sessão nada abre; uma empresa não vê catálogo, análises, jobs nem conversas da outra."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from obranexo import contas
from obranexo.config import config

CASO = "goianira_pe038_2026"


@pytest.fixture(autouse=True)
def _sem_bloqueios():
    from obranexo.api import auth

    auth._erros.clear()
    yield
    auth._erros.clear()


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setattr(config, "llm_provider", None)
    from obranexo.api import main

    main._estado.clear()
    yield main.app
    main._estado.clear()


def _analisar(c: TestClient) -> tuple[str, str]:
    r = c.post("/api/analises", json={"caso": CASO})
    assert r.status_code == 202, r.text
    job_id = r.json()["id"]
    with c.stream("GET", f"/api/jobs/{job_id}/eventos") as stream:
        for linha in stream.iter_lines():
            if linha.startswith("data: ") and '"analise_id"' in linha:
                fim = json.loads(linha[6:])
                if fim.get("status") != "executando":
                    return job_id, fim["analise_id"]
    raise AssertionError("o job não terminou")


def test_senha_com_scrypt():
    h = contas.hash_senha("uma senha qualquer")
    assert h.startswith("scrypt$") and "uma senha" not in h
    assert contas.conferir_senha("uma senha qualquer", h)
    assert not contas.conferir_senha("outra senha", h)
    assert not contas.conferir_senha("x", "formato-invalido")


def test_sem_login_so_o_publico_abre(app):
    with TestClient(app) as c:
        assert c.get("/").status_code == 200  # a interface carrega e mostra a tela de login
        assert c.get("/api/status").status_code == 200
        assert c.get("/api/conteudo/grafo").status_code == 200
        for metodo, url in [("GET", "/api/catalogo"), ("GET", "/api/analises"), ("GET", "/api/casos"), ("POST", "/api/analises"),
                            ("GET", "/api/prospeccoes"), ("POST", "/api/chat"), ("GET", "/api/metricas"), ("GET", "/api/custos"),
                            ("POST", "/api/config/llm"), ("GET", "/api/jobs/x/eventos"), ("GET", "/api/auth/eu")]:
            assert c.request(metodo, url).status_code == 401, url
        assert "empresa" not in c.get("/api/status").json()


def test_login_logout_e_bearer(app):
    empresa_id = contas.criar_empresa("Elétrica Alfa", "12345678000190")
    contas.criar_usuario("Ana@Alfa.com.br", "senha-forte-1", empresa_id, "Ana")
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"email": "ana@alfa.com.br", "senha": "errada"}).status_code == 401
        assert c.post("/api/auth/login", json={"email": "ninguem@alfa.com.br", "senha": "senha-forte-1"}).status_code == 401
        r = c.post("/api/auth/login", json={"email": " ANA@alfa.com.br ", "senha": "senha-forte-1"})
        assert r.status_code == 200
        assert "httponly" in r.headers["set-cookie"].lower() and "samesite=lax" in r.headers["set-cookie"].lower()
        token = r.json()["token"]
        eu = c.get("/api/auth/eu").json()
        assert eu["email"] == "ana@alfa.com.br" and eu["empresa"] == {"id": empresa_id, "nome": "Elétrica Alfa"} and not eu["admin"]
        c.post("/api/auth/logout")
        assert c.get("/api/auth/eu").status_code == 401
        # o token encerrado não vale mais nem por cabeçalho
        assert c.get("/api/auth/eu", headers={"Authorization": f"Bearer {token}"}).status_code == 401

    with TestClient(app) as api_cliente:
        token = api_cliente.post("/api/auth/login", json={"email": "ana@alfa.com.br", "senha": "senha-forte-1"}).json()["token"]
        api_cliente.cookies.clear()
        assert api_cliente.get("/api/catalogo", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_bloqueia_tentativas_repetidas(app):
    contas.criar_usuario("bia@beta.com.br", "senha-forte-2", contas.criar_empresa("Beta"))
    with TestClient(app) as c:
        for _ in range(5):
            assert c.post("/api/auth/login", json={"email": "bia@beta.com.br", "senha": "errada"}).status_code == 401
        assert c.post("/api/auth/login", json={"email": "bia@beta.com.br", "senha": "senha-forte-2"}).status_code == 429


def test_troca_de_senha_e_desativacao_encerram_sessoes(app):
    contas.criar_usuario("caio@gama.com.br", "senha-antiga", contas.criar_empresa("Gama"))
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"email": "caio@gama.com.br", "senha": "senha-antiga"}).status_code == 200
        contas.definir_senha("caio@gama.com.br", "senha-nova-123")
        assert c.get("/api/auth/eu").status_code == 401
        assert c.post("/api/auth/login", json={"email": "caio@gama.com.br", "senha": "senha-nova-123"}).status_code == 200
        contas.definir_ativo("caio@gama.com.br", False)
        assert c.get("/api/auth/eu").status_code == 401
        assert c.post("/api/auth/login", json={"email": "caio@gama.com.br", "senha": "senha-nova-123"}).status_code == 401


def test_so_administrador_mexe_na_plataforma(app, entrar):
    with TestClient(app) as c:
        entrar(c)
        assert c.post("/api/config/llm", json={"provedor": None}).status_code == 403
        assert c.get("/api/custos").status_code == 403
        assert c.get("/api/metricas/llm").status_code == 403
    with TestClient(app) as c:
        entrar(c, admin=True, email="admin@obranexo.com.br", empresa="ObraNexo")
        assert c.post("/api/config/llm", json={"provedor": None}).status_code == 200
        assert c.get("/api/custos").status_code == 200


def test_cadastro_fechado_por_padrao_e_aberto_por_configuracao(app, monkeypatch):
    pedido = {"empresa": "Delta Elétrica", "cnpj": "11222333000144", "email": "dora@delta.com.br", "senha": "senha-forte-3"}
    with TestClient(app) as c:
        assert c.get("/api/status").json()["cadastro_aberto"] is False
        assert c.post("/api/auth/cadastro", json=pedido).status_code == 403
        monkeypatch.setattr(config, "cadastro_aberto", True)
        assert c.post("/api/auth/cadastro", json={**pedido, "email": "invalido"}).status_code == 400
        assert contas.listar_empresas() == []  # e-mail inválido não deixa empresa órfã
        r = c.post("/api/auth/cadastro", json=pedido)
        assert r.status_code == 201 and r.json()["usuario"]["empresa"]["nome"] == "Delta Elétrica"
        assert c.get("/api/auth/eu").status_code == 200
        assert c.post("/api/auth/cadastro", json=pedido).status_code == 409


@pytest.mark.skipif(not (config.dir_casos / CASO / "contratacao.json").exists(), reason="caso congelado ausente")
def test_empresas_isoladas(app, entrar, tmp_path):
    with TestClient(app) as a, TestClient(app) as b:
        ua = entrar(a, email="ana@alfa.com.br", empresa="Alfa")
        ub = entrar(b, email="bia@beta.com.br", empresa="Beta")

        # catálogo: o que A adiciona não aparece para B
        produto = {"id": "SO-DA-ALFA", "sku": "SO-DA-ALFA", "nome": "Refletor da Alfa", "categoria": "refletor_led", "atributos": {}}
        assert a.post("/api/catalogo/produtos", json={"produtos": [produto]}).status_code == 200
        assert "SO-DA-ALFA" in {p["sku"] for p in a.get("/api/catalogo").json()["produtos"]}
        assert "SO-DA-ALFA" not in {p["sku"] for p in b.get("/api/catalogo").json()["produtos"]}
        assert (tmp_path / "empresas" / ua.empresa_id / "catalogo_ativo.json").exists()
        assert not (tmp_path / "empresas" / ub.empresa_id / "catalogo_ativo.json").exists()

        # análise: só a dona vê, baixa o dossiê, acompanha o job e revisa
        job_id, analise_id = _analisar(a)
        assert (tmp_path / "empresas" / ua.empresa_id / "analises" / f"{analise_id}.json").exists()
        assert [x["id"] for x in a.get("/api/analises").json()] == [analise_id]
        assert b.get("/api/analises").json() == []
        for url in (f"/api/analises/{analise_id}", f"/api/analises/{analise_id}/dossie.md", f"/api/analises/{analise_id}/proposta",
                    f"/api/analises/{analise_id}/chamadas", f"/api/jobs/{job_id}", f"/api/jobs/{job_id}/eventos"):
            assert a.get(url).status_code == 200, url
            assert b.get(url).status_code == 404, url
        assert b.patch(f"/api/analises/{analise_id}/revisao", json={"status": "REJEITADO"}).status_code == 404
        caso_a = next(x for x in a.get("/api/casos").json() if x["nome"] == CASO)
        caso_b = next(x for x in b.get("/api/casos").json() if x["nome"] == CASO)
        assert len(caso_a["analises"]) == 1 and caso_b["analises"] == []  # os editais são públicos; as análises, não
        assert b.get("/api/metricas").json()["analises"] == 0


def test_conversas_do_assistente_isoladas():
    from obranexo.storage import chat

    alfa, beta = contas.criar_empresa("Alfa"), contas.criar_empresa("Beta")
    with contas.na_empresa(alfa):
        chat.salvar_mensagem("sessao-1", "Alfa", 0, {"papel": "usuario", "texto": "segredo da Alfa"})
        assert chat.carregar("sessao-1")[0]["texto"] == "segredo da Alfa"
    with contas.na_empresa(beta):
        assert chat.carregar("sessao-1") == []
    assert chat.carregar("sessao-1") == []  # nem sem empresa ativa
