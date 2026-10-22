"""Persistência simples das análises em JSON (v0.1). Na v0.2 migra para PostgreSQL."""

from __future__ import annotations

from pathlib import Path

from obranexo.config import config
from obranexo.models import Analise


def _dir() -> Path:
    config.dir_analises.mkdir(parents=True, exist_ok=True)
    return config.dir_analises


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
