"""Contexto compartilhado entre os nós do fluxo agêntico."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field

from obranexo.config import Config, config
from obranexo.documents.extract import IndiceDocumentos
from obranexo.llm.client import LLMClient
from obranexo.models import Analise, Empresa, EventoLog, Evidencia

OnEvento = Callable[[EventoLog], None]


@dataclass
class Contexto:
    analise: Analise
    empresa: Empresa
    indice: IndiceDocumentos
    llm: LLMClient
    cfg: Config = field(default_factory=lambda: config)
    on_evento: OnEvento | None = None
    _seq: itertools.count = field(default_factory=itertools.count)

    def evento(self, no: str, mensagem: str, **dados) -> None:
        ev = EventoLog(no=no, mensagem=mensagem, dados=dados)
        self.analise.log.append(ev)
        if self.on_evento:
            self.on_evento(ev)

    def novo_id(self, prefixo: str) -> str:
        return f"{prefixo}-{next(self._seq):04d}"

    def nova_evidencia(self, documento_id: str, pagina: int | None, trecho: str) -> Evidencia:
        ev = Evidencia(id=self.novo_id("ev"), documento_id=documento_id, pagina=pagina, trecho_literal=trecho.strip())
        self.analise.evidencias.append(ev)
        return ev

    @property
    def usar_llm(self) -> bool:
        return self.llm.disponivel and not self.llm.excedeu_orcamento()
