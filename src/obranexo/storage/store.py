"""Persistência simples em JSON (v0.1): análises, prospecções e catálogo ativo. Na v0.2 migra para PostgreSQL.

Com uma empresa ativa (contas.empresa_ativa, definida pelo login na API), tudo fica em data/empresas/<id>/ e uma
empresa não enxerga os arquivos da outra; sem empresa ativa (linha de comando, testes), nos diretórios de sempre.
"""

from __future__ import annotations

import json
from pathlib import Path

from obranexo import contas
from obranexo.config import config
from obranexo.models import Analise, Empresa, Prospeccao


def _base() -> Path:
    empresa_id = contas.empresa_ativa()
    return contas.dir_empresa(empresa_id) if empresa_id else config.dir_dados


def _dir() -> Path:
    d = _base() / "analises" if contas.empresa_ativa() else config.dir_analises
    d.mkdir(parents=True, exist_ok=True)
    return d


def salvar(analise: Analise) -> Path:
    caminho = _dir() / f"{analise.id}.json"
    caminho.write_text(analise.model_dump_json(indent=1), encoding="utf-8")
    return caminho


def carregar(analise_id: str) -> Analise | None:
    caminho = _dir() / f"{analise_id}.json"
    if not caminho.exists():
        return None
    return Analise.model_validate_json(caminho.read_text(encoding="utf-8"))


def listar() -> list[Analise]:
    analises = []
    for p in sorted(_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            analises.append(Analise.model_validate_json(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return analises


# ---------------------------------------------------------------------------- prospecções


def _dir_prospeccoes() -> Path:
    d = _base() / "prospeccoes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def salvar_prospeccao(p: Prospeccao) -> Path:
    caminho = _dir_prospeccoes() / f"{p.id}.json"
    caminho.write_text(p.model_dump_json(indent=1), encoding="utf-8")
    return caminho


def carregar_prospeccao(prospeccao_id: str) -> Prospeccao | None:
    caminho = _dir_prospeccoes() / f"{prospeccao_id}.json"
    if not caminho.exists():
        return None
    return Prospeccao.model_validate_json(caminho.read_text(encoding="utf-8"))


def listar_prospeccoes() -> list[Prospeccao]:
    saida = []
    for p in sorted(_dir_prospeccoes().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            saida.append(Prospeccao.model_validate_json(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return saida


# ---------------------------------------------------------------------------- catálogo ativo


def caminho_catalogo_ativo() -> Path:
    return _base() / "catalogo_ativo.json"


def salvar_catalogo(empresa: Empresa) -> Path:
    """Grava no mesmo formato do catálogo demonstrativo (relido por carregar_catalogo_json)."""
    caminho = caminho_catalogo_ativo()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    dados = {
        "empresa": empresa.model_dump(mode="json", exclude={"produtos"}),
        "produtos": [p.model_dump(mode="json") for p in empresa.produtos],
    }
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    return caminho


def remover_catalogo_ativo() -> None:
    caminho_catalogo_ativo().unlink(missing_ok=True)
