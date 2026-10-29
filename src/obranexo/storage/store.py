"""Persistência simples em JSON (v0.1): análises, prospecções e catálogo ativo. Na v0.2 migra para PostgreSQL.

Com uma empresa ativa (contas.empresa_ativa, definida pelo login na API), tudo fica em data/empresas/<id>/ e uma
empresa não enxerga os arquivos da outra; sem empresa ativa (linha de comando, testes), nos diretórios de sempre.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from obranexo import contas
from obranexo.config import config
from obranexo.connectors import pncp
from obranexo.models import Analise, Empresa, Prospeccao

# Licitações baixadas do PNCP têm nome CNPJ_ANO_SEQ; os casos de demonstração (versionados) têm nome legível
COLETADO = re.compile(r"^\d+_\d+_\d+$")


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


# ---------------------------------------------------------------------------- casos (licitações congeladas)


def dir_casos() -> Path:
    """Onde gravar uma licitação coletada: na pasta da empresa ativa, para nenhuma outra saber o que ela baixou."""
    empresa_id = contas.empresa_ativa()
    return contas.dir_empresa(empresa_id) / "casos" if empresa_id else config.dir_casos


def casos_de_demonstracao() -> list[Path]:
    return [p for p in pncp.listar_casos(config.dir_casos) if not COLETADO.match(p.name)]


def listar_casos() -> list[Path]:
    """Os casos de demonstração (comuns a todas) mais os coletados pela empresa ativa. Fora da API, data/casos inteiro.

    Licitações coletadas em data/casos antes da separação por empresa não aparecem para nenhuma empresa:
    não há como saber de quem eram. Coletar de novo é rápido (o PNCP fica em cache)."""
    if not contas.empresa_ativa():
        return pncp.listar_casos(config.dir_casos)
    return sorted(casos_de_demonstracao() + pncp.listar_casos(dir_casos()), key=lambda p: p.name)


def caso(nome: str) -> Path | None:
    """Pasta de um caso visível para a empresa ativa, ou None (nome inexistente, de outra empresa ou fora das pastas)."""
    return next((p for p in listar_casos() if p.name == nome), None)


def pastas_de_casos() -> list[Path]:
    """Pastas onde podem estar os anexos dos casos da empresa ativa (para servir um documento com segurança)."""
    return [config.dir_casos, dir_casos()] if contas.empresa_ativa() else [config.dir_casos]


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
