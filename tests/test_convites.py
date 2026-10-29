"""Convite para criar conta e link de nova senha: tudo pela interface, com ou sem e-mail configurado."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from obranexo import contas, db, notificacoes
from obranexo.config import config

SENHA = "senha-de-teste"


@pytest.fixture()
def app(monkeypatch):
    from obranexo.api import auth, main

    monkeypatch.setattr(config, "smtp_host", None)
    auth._erros.clear()
    main._estado.clear()
    yield main.app
    auth._erros.clear()
    main._estado.clear()


def _token(link: str) -> str:
    return link.rsplit("/", 1)[-1]


def test_colega_convidado_entra_na_mesma_empresa(app, entrar):
    with TestClient(app) as ana, TestClient(app) as novo:
        u = entrar(ana, email="ana@alfa.com.br", empresa="Alfa")
        r = ana.post("/api/equipe/convites", json={"email": "Caio@Alfa.com.br"})
        assert r.status_code == 201, r.text
        assert r.json()["enviado"] is False and r.json()["link"].startswith(f"{config.url_publica}/#/convite/")
        token = _token(r.json()["link"])
        assert [c["email"] for c in ana.get("/api/equipe").json()["convites"]] == ["caio@alfa.com.br"]

        assert novo.post("/api/auth/convites/ver", json={"token": token}).json() == {"email": "caio@alfa.com.br", "empresa": "Alfa"}
        r = novo.post("/api/auth/convites/aceitar", json={"token": token, "senha": "outra-senha-1", "nome": "Caio"})
        assert r.status_code == 200, r.text
        assert novo.get("/api/auth/eu").json()["empresa"]["id"] == u.empresa_id
        assert {x["email"] for x in ana.get("/api/equipe").json()["usuarios"]} == {"ana@alfa.com.br", "caio@alfa.com.br"}
        assert ana.get("/api/equipe").json()["convites"] == []

        # uso único
        assert novo.post("/api/auth/convites/ver", json={"token": token}).status_code == 404
        assert novo.post("/api/auth/convites/aceitar", json={"token": token, "senha": "outra-senha-1"}).status_code == 400


def test_so_administrador_convida_outra_empresa(app, entrar):
    with TestClient(app) as ana, TestClient(app) as adm, TestClient(app) as novo:
        entrar(ana, email="ana@alfa.com.br", empresa="Alfa")
        entrar(adm, email="adm@obranexo.com.br", empresa="ObraNexo", admin=True)
        assert ana.post("/api/equipe/convites", json={"email": "x@beta.com.br", "empresa_nova": "Beta"}).status_code == 403
        assert ana.post("/api/equipe/convites", json={"email": "x@alfa.com.br", "admin": True}).status_code == 403
        r = adm.post("/api/equipe/convites", json={"email": "bia@beta.com.br", "empresa_nova": "Beta Elétrica"})
        token = _token(r.json()["link"])
        assert novo.post("/api/auth/convites/ver", json={"token": token}).json()["empresa"] == "Beta Elétrica"
        assert novo.post("/api/auth/convites/aceitar", json={"token": token, "senha": "senha-da-bia"}).status_code == 200
        eu = novo.get("/api/auth/eu").json()
        assert eu["empresa"]["nome"] == "Beta Elétrica" and eu["admin"] is False
        assert adm.get("/api/equipe").json()["convites"] == []  # o convite da Beta não aparece na equipe de quem convidou


def test_convite_recusado_para_email_com_conta_ou_invalido(app, entrar):
    with TestClient(app) as ana:
        entrar(ana, email="ana@alfa.com.br", empresa="Alfa")
        assert ana.post("/api/equipe/convites", json={"email": "ana@alfa.com.br"}).status_code == 400
        assert ana.post("/api/equipe/convites", json={"email": "sem-arroba"}).status_code == 400


def test_convite_expirado_ou_cancelado_nao_vale(app, entrar):
    with TestClient(app) as ana, TestClient(app) as bia, TestClient(app) as novo:
        entrar(ana, email="ana@alfa.com.br", empresa="Alfa")
        entrar(bia, email="bia@beta.com.br", empresa="Beta")
        token = _token(ana.post("/api/equipe/convites", json={"email": "caio@alfa.com.br"}).json()["link"])
        convite_id = ana.get("/api/equipe").json()["convites"][0]["id"]
        assert bia.delete(f"/api/equipe/convites/{convite_id}").status_code == 404  # convite de outra empresa
        assert ana.delete(f"/api/equipe/convites/{convite_id}").status_code == 200
        assert novo.post("/api/auth/convites/ver", json={"token": token}).status_code == 404

        token = _token(ana.post("/api/equipe/convites", json={"email": "dani@alfa.com.br"}).json()["link"])
        with db.escrever() as con:
            con.execute(text("UPDATE links_conta SET expira_em = '2000-01-01T00:00:00' WHERE email = 'dani@alfa.com.br'"))
        assert novo.post("/api/auth/convites/aceitar", json={"token": token, "senha": "senha-da-dani"}).status_code == 400


def test_novo_convite_substitui_o_anterior(app, entrar):
    with TestClient(app) as ana:
        entrar(ana, email="ana@alfa.com.br", empresa="Alfa")
        primeiro = _token(ana.post("/api/equipe/convites", json={"email": "caio@alfa.com.br"}).json()["link"])
        segundo = _token(ana.post("/api/equipe/convites", json={"email": "caio@alfa.com.br"}).json()["link"])
        assert ana.post("/api/auth/convites/ver", json={"token": primeiro}).status_code == 404
        assert ana.post("/api/auth/convites/ver", json={"token": segundo}).status_code == 200


def test_esqueci_a_senha(app, entrar, monkeypatch):
    enviados: list[tuple[str, str]] = []
    monkeypatch.setattr(notificacoes, "enviar_redefinicao", lambda para, token: enviados.append((para, token)) or True)
    with TestClient(app) as ana, TestClient(app) as anonimo:
        entrar(ana, email="ana@alfa.com.br", empresa="Alfa")
        com_conta = anonimo.post("/api/auth/recuperar", json={"email": "ANA@alfa.com.br"})
        sem_conta = anonimo.post("/api/auth/recuperar", json={"email": "ninguem@alfa.com.br"})
        assert com_conta.status_code == sem_conta.status_code == 202
        assert com_conta.json() == sem_conta.json()  # não revela quais e-mails têm conta
        assert [p for p, _ in enviados] == ["ana@alfa.com.br"]

        r = anonimo.post("/api/auth/redefinir", json={"token": enviados[0][1], "senha": "senha-nova-123"})
        assert r.status_code == 200 and anonimo.get("/api/auth/eu").json()["email"] == "ana@alfa.com.br"
        assert ana.get("/api/auth/eu").status_code == 401  # a sessão antiga foi encerrada
        assert contas.autenticar("ana@alfa.com.br", SENHA) is None
        assert contas.autenticar("ana@alfa.com.br", "senha-nova-123") is not None
        assert anonimo.post("/api/auth/redefinir", json={"token": enviados[0][1], "senha": "mais-uma-senha"}).status_code == 400


def test_pedidos_de_nova_senha_tem_limite(app):
    with TestClient(app) as c:
        for _ in range(5):
            assert c.post("/api/auth/recuperar", json={"email": "ana@alfa.com.br"}).status_code == 202
        assert c.post("/api/auth/recuperar", json={"email": "ana@alfa.com.br"}).status_code == 429


def test_administrador_gera_link_de_nova_senha(app, entrar):
    with TestClient(app) as ana, TestClient(app) as adm:
        entrar(ana, email="ana@alfa.com.br", empresa="Alfa")
        entrar(adm, email="adm@obranexo.com.br", empresa="ObraNexo", admin=True)
        assert ana.post("/api/equipe/redefinicoes", json={"email": "ana@alfa.com.br"}).status_code == 403
        assert adm.post("/api/equipe/redefinicoes", json={"email": "ninguem@x.com.br"}).status_code == 404
        r = adm.post("/api/equipe/redefinicoes", json={"email": "ana@alfa.com.br"})
        assert r.status_code == 201 and "/#/redefinir/" in r.json()["link"]


def test_email_vai_pelo_smtp_quando_configurado(app, entrar, monkeypatch):
    mensagens = []

    class _SMTP:
        def __init__(self, host, porta, timeout):
            assert (host, porta) == ("smtp.exemplo.com.br", 587)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def starttls(self):
            pass

        def login(self, usuario, senha):
            assert (usuario, senha) == ("robo", "segredo")

        def send_message(self, msg):
            mensagens.append(msg)

    monkeypatch.setattr(notificacoes.smtplib, "SMTP", _SMTP)
    for campo, valor in {"smtp_host": "smtp.exemplo.com.br", "smtp_usuario": "robo", "smtp_senha": "segredo",
                         "smtp_remetente": "nao-responda@obranexo.com.br"}.items():
        monkeypatch.setattr(config, campo, valor)
    with TestClient(app) as ana:
        entrar(ana, email="ana@alfa.com.br", empresa="Alfa")
        r = ana.post("/api/equipe/convites", json={"email": "caio@alfa.com.br"}).json()
        assert r["enviado"] is True
        assert mensagens[0]["To"] == "caio@alfa.com.br" and r["link"] in mensagens[0].get_content()


def test_tela_equipe_e_servida(app):
    with TestClient(app) as c:
        assert c.get("/js/views/equipe.js").status_code == 200
