"""Jobs sobrevivem a um reinício do servidor: o estado fica no banco e o que estava em andamento é retomado ou interrompido."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from obranexo import contas
from obranexo.api.jobs import INTERROMPIDO, Job, jobs
from obranexo.config import config

CASO = "goianira_pe038_2026"
pytestmark = pytest.mark.skipif(not (config.dir_casos / CASO / "contratacao.json").exists(), reason="caso congelado ausente")


@pytest.fixture()
def app(monkeypatch):
    from obranexo.api import auth, main

    monkeypatch.setattr(config, "llm_provider", None)
    auth._erros.clear()
    main._estado.clear()
    jobs._jobs.clear()
    yield main.app
    jobs._jobs.clear()
    main._estado.clear()


def _esperar(c: TestClient, job_id: str) -> dict:
    for _ in range(200):
        j = c.get(f"/api/jobs/{job_id}").json()
        if j["status"] != "executando":
            return j
        time.sleep(0.05)
    raise AssertionError("o job não terminou")


def _reiniciar() -> None:
    """O que um novo processo vê: nada em memória, só o banco."""
    jobs._jobs.clear()


def test_job_concluido_continua_consultavel_depois_do_reinicio(app, entrar):
    with TestClient(app) as a, TestClient(app) as b:
        entrar(a, email="ana@alfa.com.br", empresa="Alfa")
        entrar(b, email="bia@beta.com.br", empresa="Beta")
        job_id = a.post("/api/analises", json={"caso": CASO}).json()["id"]
        antes = _esperar(a, job_id)
        _reiniciar()
        depois = a.get(f"/api/jobs/{job_id}").json()
        assert depois["status"] == "concluida" and depois["analise_id"] == antes["analise_id"]
        assert [e["mensagem"] for e in depois["log"]] == [e["mensagem"] for e in antes["log"]]
        assert b.get(f"/api/jobs/{job_id}").status_code == 404  # continua só da dona
        with a.stream("GET", f"/api/jobs/{job_id}/eventos") as stream:
            assert any(linha.startswith("event: fim") for linha in stream.iter_lines())


def _job_que_estava_rodando(empresa_id: str, tipo: str, alvo: str, **parametros) -> Job:
    with contas.na_empresa(empresa_id):
        job = Job(id=f"caiu-{tipo}", tipo=tipo, alvo=alvo, parametros=parametros)
        job.gravar()
    return job


def test_analise_interrompida_recomeca_com_o_mesmo_id(app, entrar):
    with TestClient(app) as a:
        usuario = entrar(a, email="ana@alfa.com.br", empresa="Alfa")
    _job_que_estava_rodando(usuario.empresa_id, "analise", CASO, caso=CASO)
    _reiniciar()
    with TestClient(app) as a:  # a subida do app retoma o que ficou em andamento
        entrar(a, email="ana2@alfa.com.br", empresa="Alfa 2")  # outra empresa não vê o job
        assert a.get("/api/jobs/caiu-analise").status_code == 404
    with TestClient(app) as a:
        a.post("/api/auth/login", json={"email": "ana@alfa.com.br", "senha": "senha-de-teste"})
        j = _esperar(a, "caiu-analise")
        assert j["status"] == "concluida", j
        assert "O servidor reiniciou: a tarefa recomeçou do início." in [e["mensagem"] for e in j["log"]]
        assert a.get(f"/api/analises/{j['analise_id']}").status_code == 200


@pytest.mark.parametrize("tipo, alvo, parametros", [
    ("prospeccao", "GO", {}),       # gastaria cota de IA sem ninguém pedir
    ("chat", "sessao-1", {}),
    ("analise", "caso-apagado", {"caso": "caso-apagado"}),  # o caso não existe mais
])
def test_o_que_nao_da_para_retomar_fica_interrompido(app, entrar, tipo, alvo, parametros):
    with TestClient(app) as a:
        usuario = entrar(a, email="ana@alfa.com.br", empresa="Alfa")
        _job_que_estava_rodando(usuario.empresa_id, tipo, alvo, **parametros)
        _reiniciar()
    with TestClient(app) as a:
        a.post("/api/auth/login", json={"email": "ana@alfa.com.br", "senha": "senha-de-teste"})
        j = a.get(f"/api/jobs/caiu-{tipo}").json()
        assert j["status"] == "erro" and j["erro"] == INTERROMPIDO
