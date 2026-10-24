"""Contexto compartilhado entre os nós do fluxo agêntico."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field

from obranexo.config import Config, config
from obranexo.documents.extract import IndiceDocumentos
from obranexo.llm.client import LLMClient
from obranexo.models import Analise, Documento, Empresa, EventoLog, Evidencia, ItemDemanda
from obranexo.observability import logs

OnEvento = Callable[[EventoLog], None]


@dataclass
class Contexto:
    """Estado compartilhado da análise: os nós do grafo (agents/grafo.py) só se comunicam por aqui.

    `analise` é o que fica salvo (itens, requisitos, evidências, correspondências, conflitos, dossiê, trilha);
    `indice` é o texto dos documentos, por página, com busca; os demais campos são de trabalho, entre nós."""

    analise: Analise
    empresa: Empresa
    indice: IndiceDocumentos
    llm: LLMClient
    cfg: Config = field(default_factory=lambda: config)
    on_evento: OnEvento | None = None
    documentos_entrada: list[Documento] = field(default_factory=list)  # anexos da contratação, antes da indexação
    relevantes: list[ItemDemanda] = field(default_factory=list)  # itens nas categorias do catálogo (filtrar_relevantes)
    afetados: list[ItemDemanda] = field(default_factory=list)  # itens que ganharam requisitos com o Investigador
    plano: tuple[str, list[str], list[str]] | None = None  # (resumo executivo, próximos passos, riscos) do Planejador
    _seq: itertools.count = field(default_factory=itertools.count)

    def evento(self, no: str, mensagem: str, **dados) -> None:
        ev = EventoLog(no=no, mensagem=mensagem, dados=dados)
        self.analise.log.append(ev)
        # O mesmo evento vai para o log estruturado: a trilha da análise também existe fora do JSON dela
        logs.registrar("etapa", **{"analise_id": self.analise.id, "no": no, "mensagem": mensagem, **dados})
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
