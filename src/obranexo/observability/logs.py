"""Logs estruturados com a biblioteca padrão: uma linha por evento, com campos fixos.

Dois tipos de evento passam por aqui: cada etapa do fluxo (Contexto.evento) e cada chamada de modelo
(Trilha.gravar). Com OBRANEXO_LOG_JSON=1 a saída é JSON por linha, pronta para qualquer agregador de logs;
sem a variável, uma linha legível para o terminal. Configurado uma vez, no servidor e na CLI.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import Any

logger = logging.getLogger("obranexo")


class _FormatadorJSON(logging.Formatter):
    def format(self, registro: logging.LogRecord) -> str:
        linha = {"ts": datetime.fromtimestamp(registro.created).isoformat(timespec="milliseconds"), "nivel": registro.levelname, "evento": registro.getMessage()}
        linha.update(getattr(registro, "campos", {}) or {})
        return json.dumps(linha, ensure_ascii=False, default=str)


class _FormatadorTexto(logging.Formatter):
    def format(self, registro: logging.LogRecord) -> str:
        campos = getattr(registro, "campos", {}) or {}
        extra = " ".join(f"{k}={_curto(v)}" for k, v in campos.items() if v not in (None, "", 0, False))
        return f"{datetime.fromtimestamp(registro.created):%H:%M:%S} {registro.getMessage()} {extra}".rstrip()


def _curto(valor: Any) -> str:
    texto = str(valor)
    return texto if len(texto) <= 80 else texto[:77] + "…"


def configurar(json_: bool | None = None, nivel: int = logging.INFO) -> None:
    """Instala um único handler em stderr. Chamar mais de uma vez não duplica a saída."""
    if json_ is None:
        from obranexo.config import config

        json_ = config.log_json
    for h in list(logger.handlers):
        logger.removeHandler(h)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_FormatadorJSON() if json_ else _FormatadorTexto())
    logger.addHandler(handler)
    logger.setLevel(nivel)
    logger.propagate = False


def registrar(evento: str, nivel: int = logging.INFO, **campos: Any) -> None:
    logger.log(nivel, evento, extra={"campos": campos})
