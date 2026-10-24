"""Isolamento dos testes: nada do que um teste grava vai para os dados reais do servidor.

Os diretórios de dados gerados (análises, prospecções, catálogo ativo e o SQLite da trilha de chamadas e do chat)
passam a apontar para um diretório temporário em cada teste. Os pacotes congelados (data/casos), o catálogo demo e
o cache de respostas de modelo continuam nos lugares reais: são insumo, não saída.
"""

from __future__ import annotations

import pytest

from obranexo.config import config


@pytest.fixture(autouse=True)
def _dados_isolados(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "dir_dados", tmp_path)
    monkeypatch.setattr(config, "dir_analises", tmp_path / "analises")
