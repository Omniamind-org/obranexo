"""Verificação de evidências: toda citação precisa existir no texto de origem."""

from __future__ import annotations

from rapidfuzz import fuzz

from obranexo.documents.extract import IndiceDocumentos, normalizar_busca
from obranexo.models import Evidencia

LIMIAR_CITACAO = 90.0


def verificar_evidencia(ev: Evidencia, indice: IndiceDocumentos) -> Evidencia:
    """Marca a evidência como verificada se o trecho literal aparece na página citada
    (ou em qualquer página do documento, com score menor)."""
    alvo = normalizar_busca(ev.trecho_literal)
    if not alvo:
        ev.verificada, ev.score_match = False, 0.0
        return ev
    paginas = indice.paginas.get(ev.documento_id)
    if not paginas:
        ev.verificada, ev.score_match = False, 0.0
        return ev
    candidatas = [ev.pagina] if ev.pagina and 1 <= ev.pagina <= len(paginas) else list(range(1, len(paginas) + 1))
    melhor = 0.0
    for p in candidatas:
        score = fuzz.partial_ratio(alvo, normalizar_busca(paginas[p - 1]))
        melhor = max(melhor, score)
        if score >= LIMIAR_CITACAO:
            break
    if melhor < LIMIAR_CITACAO and ev.pagina:
        # Procura no documento inteiro: se achar, corrige a página em vez de reprovar
        for p, texto in enumerate(paginas, start=1):
            score = fuzz.partial_ratio(alvo, normalizar_busca(texto))
            if score >= LIMIAR_CITACAO:
                ev.pagina = p
                melhor = score
                break
    ev.score_match = round(float(melhor), 1)
    ev.verificada = melhor >= LIMIAR_CITACAO
    return ev
