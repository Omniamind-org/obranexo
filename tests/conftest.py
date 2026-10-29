"""Isolamento dos testes: nada do que um teste grava vai para os dados reais do servidor.

Os diretórios de dados gerados (análises, prospecções, catálogo ativo e o SQLite da trilha de chamadas e do chat)
passam a apontar para um diretório temporário em cada teste. Os pacotes congelados (data/casos), o catálogo demo e
o cache de respostas de modelo continuam nos lugares reais: são insumo, não saída.
"""

from __future__ import annotations

import pytest

from obranexo.config import config


def _entrar(client, *, admin: bool = False, email: str = "fornecedor@exemplo.com.br", empresa: str = "Fornecedor Teste"):
    """Cria empresa e usuário no banco do teste e faz login no TestClient (o cookie de sessão fica no cliente)."""
    from obranexo import contas

    usuario = contas.criar_usuario(email, "senha-de-teste", contas.criar_empresa(empresa), admin=admin)
    r = client.post("/api/auth/login", json={"email": email, "senha": "senha-de-teste"})
    assert r.status_code == 200, r.text
    return usuario


@pytest.fixture()
def entrar():
    """Login na API: `usuario = entrar(client, admin=True)`."""
    return _entrar


@pytest.fixture(autouse=True)
def _dados_isolados(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "dir_dados", tmp_path)
    monkeypatch.setattr(config, "dir_analises", tmp_path / "analises")
