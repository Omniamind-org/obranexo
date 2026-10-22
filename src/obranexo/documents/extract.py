"""Extração de texto de PDFs com número de página e índice de busca textual.

Cada trecho guarda (documento, página, ordem) para que toda citação do sistema
possa ser aberta no lugar exato do documento original.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from rapidfuzz import fuzz

from obranexo.models import Documento, Trecho

TAMANHO_TRECHO = 700
_STOPWORDS = {"para", "com", "sem", "dos", "das", "nos", "nas", "por", "que", "uma", "the"}


def extrair_paginas(caminho: Path) -> list[str]:
    """Texto de cada página do PDF (lista indexada a partir de 0)."""
    import pymupdf

    paginas: list[str] = []
    with pymupdf.open(caminho) as pdf:
        for pagina in pdf:
            texto = pagina.get_text("text")
            texto = re.sub(r"[ \t\xa0]+", " ", texto)
            texto = re.sub(r"\n{3,}", "\n\n", texto)
            paginas.append(texto.strip())
    return paginas


def gerar_trechos(documento_id: str, paginas: list[str], tamanho: int = TAMANHO_TRECHO) -> list[Trecho]:
    trechos: list[Trecho] = []
    ordem = 0
    for idx, texto in enumerate(paginas, start=1):
        if not texto:
            continue
        paragrafos = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]
        atual = ""
        for paragrafo in paragrafos:
            if atual and len(atual) + len(paragrafo) > tamanho:
                trechos.append(Trecho(id=f"{documento_id}:p{idx}:{ordem}", documento_id=documento_id, pagina=idx, ordem=ordem, texto=atual))
                ordem += 1
                atual = paragrafo
            else:
                atual = f"{atual}\n{paragrafo}" if atual else paragrafo
            # Parágrafos muito longos (listas de especificação) são fatiados por tamanho
            while len(atual) > tamanho * 2:
                corte = atual.rfind(" ", 0, tamanho)
                corte = corte if corte > tamanho // 2 else tamanho
                trechos.append(Trecho(id=f"{documento_id}:p{idx}:{ordem}", documento_id=documento_id, pagina=idx, ordem=ordem, texto=atual[:corte]))
                ordem += 1
                atual = atual[corte:].lstrip()
        if atual:
            trechos.append(Trecho(id=f"{documento_id}:p{idx}:{ordem}", documento_id=documento_id, pagina=idx, ordem=ordem, texto=atual))
            ordem += 1
    return trechos


def normalizar_busca(texto: str) -> str:
    import unicodedata

    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto.lower()).strip()


@dataclass
class ResultadoBusca:
    trecho: Trecho
    score: float


@dataclass
class IndiceDocumentos:
    """Índice em memória dos documentos de uma contratação (texto por página + trechos)."""

    documentos: dict[str, Documento] = field(default_factory=dict)
    paginas: dict[str, list[str]] = field(default_factory=dict)
    trechos: list[Trecho] = field(default_factory=list)
    _norm: dict[str, str] = field(default_factory=dict)

    def adicionar(self, documento: Documento) -> None:
        self.documentos[documento.id] = documento
        if not documento.extraivel or not documento.caminho_local:
            return
        caminho = Path(documento.caminho_local)
        if not caminho.exists():
            documento.extraivel = False
            return
        try:
            paginas = extrair_paginas(caminho)
        except Exception:  # PDF corrompido ou protegido
            documento.extraivel = False
            return
        documento.paginas = len(paginas)
        documento.extraivel = any(p.strip() for p in paginas)
        self.paginas[documento.id] = paginas
        novos = gerar_trechos(documento.id, paginas)
        self.trechos.extend(novos)
        for t in novos:
            self._norm[t.id] = normalizar_busca(t.texto)

    def adicionar_texto(self, documento: Documento, texto: str) -> None:
        """Registra um documento virtual (ex.: o registro de item do PNCP) como uma única página."""
        self.documentos[documento.id] = documento
        documento.paginas = 1
        self.paginas[documento.id] = [texto]
        novos = gerar_trechos(documento.id, [texto])
        self.trechos.extend(novos)
        for t in novos:
            self._norm[t.id] = normalizar_busca(t.texto)

    def listar(self) -> list[dict]:
        return [
            {
                "documento_id": d.id,
                "nome": d.nome,
                "tipo": d.tipo_doc,
                "paginas": d.paginas,
                "texto_extraivel": d.extraivel,
            }
            for d in self.documentos.values()
        ]

    def ler_pagina(self, documento_id: str, pagina: int) -> str | None:
        paginas = self.paginas.get(documento_id)
        if not paginas or pagina < 1 or pagina > len(paginas):
            return None
        return paginas[pagina - 1]

    def buscar(self, consulta: str, top_k: int = 5, documento_id: str | None = None, exigir_todas: bool = False) -> list[ResultadoBusca]:
        """Busca híbrida: contagem de palavras-chave + similaridade parcial (rapidfuzz).
        Com `exigir_todas`, só devolve trechos que contêm todas as palavras da consulta."""
        consulta_norm = normalizar_busca(consulta)
        palavras = [p for p in re.findall(r"[a-z0-9/+]{3,}", consulta_norm) if p not in _STOPWORDS]
        resultados: list[ResultadoBusca] = []
        for trecho in self.trechos:
            if documento_id and trecho.documento_id != documento_id:
                continue
            texto = self._norm[trecho.id]
            acertos = sum(1 for p in palavras if p in texto)
            if palavras and (acertos == 0 or (exigir_todas and acertos < len(palavras))):
                continue
            cobertura = acertos / len(palavras) if palavras else 0
            similar = fuzz.partial_token_set_ratio(consulta_norm, texto) / 100
            # Desempate: trechos que repetem os termos e trazem números (prazos, anos, valores) tendem a ser a cláusula útil
            frequencia = sum(texto.count(p) for p in palavras)
            bonus = 0.04 * min(frequencia, 5) / 5 + (0.03 if re.search(r"\d", texto) else 0)
            score = 0.63 * cobertura + 0.30 * similar + bonus
            resultados.append(ResultadoBusca(trecho=trecho, score=round(score, 4)))
        resultados.sort(key=lambda r: r.score, reverse=True)
        return resultados[:top_k]

    def texto_documento(self, documento_id: str) -> str:
        return "\n".join(self.paginas.get(documento_id, []))
