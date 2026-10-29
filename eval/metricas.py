"""Métricas da avaliação: matriz de confusão, precisão e recall por classe, consistência entre execuções e a
concordância entre os dois revisores do gabarito (kappa de Cohen). Sem dependências além da biblioteca padrão."""

from __future__ import annotations

import unicodedata
from collections import Counter

CLASSES = ("COMPATIVEL", "PARCIAL", "INDETERMINADO", "INCOMPATIVEL", "FORA_DO_PORTFOLIO")


def normalizar_rotulo(rotulo: str | None) -> str | None:
    """'Compatível', 'COMPATIVEL', 'fora' → a classe canônica; vazio → None; desconhecido → ValueError."""
    if rotulo is None or not str(rotulo).strip():
        return None
    t = unicodedata.normalize("NFKD", str(rotulo).strip().upper())
    t = "".join(c for c in t if not unicodedata.combining(c)).replace(" ", "_")
    if t in {"FORA", "FORA_DO_PORTFOLIO", "FORA_PORTFOLIO"}:
        return "FORA_DO_PORTFOLIO"
    if t not in CLASSES:
        raise ValueError(f"rótulo desconhecido: {rotulo!r} (use {', '.join(CLASSES)} ou FORA)")
    return t


def matriz_confusao(pares: list[tuple[str, str]]) -> dict[str, dict[str, int]]:
    """pares (esperado, obtido) → matriz[esperado][obtido], com todas as classes, mesmo as zeradas."""
    m = {e: {o: 0 for o in CLASSES} for e in CLASSES}
    for esperado, obtido in pares:
        m[esperado][obtido] += 1
    return m


def por_classe(m: dict[str, dict[str, int]]) -> dict[str, dict[str, float | int | None]]:
    """Precisão (dos que o sistema disse X, quantos eram X), recall (dos que eram X, quantos ele achou) e suporte."""
    saida = {}
    for c in CLASSES:
        acertos = m[c][c]
        previstos = sum(m[e][c] for e in CLASSES)
        reais = sum(m[c].values())
        saida[c] = {
            "precisao": round(acertos / previstos, 4) if previstos else None,
            "recall": round(acertos / reais, 4) if reais else None,
            "suporte": reais,
        }
    return saida


def consistencia(execucoes: list[dict[str, str]]) -> float | None:
    """Fração de itens com o mesmo resultado em todas as execuções (chave: caso/item). Uma execução só: None."""
    if len(execucoes) < 2:
        return None
    chaves = set().union(*execucoes)
    if not chaves:
        return None
    iguais = sum(1 for k in chaves if len({e.get(k) for e in execucoes}) == 1)
    return round(iguais / len(chaves), 4)


def kappa(pares: list[tuple[str, str]]) -> float | None:
    """Kappa de Cohen entre dois revisores: 1 = concordância total; 0 = o esperado por acaso. None sem itens."""
    n = len(pares)
    if not n:
        return None
    observada = sum(a == b for a, b in pares) / n
    fa, fb = Counter(a for a, _ in pares), Counter(b for _, b in pares)
    esperada = sum(fa[c] * fb[c] for c in set(fa) | set(fb)) / (n * n)
    if esperada == 1:
        return 1.0  # os dois deram o mesmo rótulo a tudo
    return round((observada - esperada) / (1 - esperada), 4)


def _pct(v: float | None) -> str:
    return "—" if v is None else f"{v:.0%}"


def markdown(metricas: dict, matriz: dict[str, dict[str, int]], classes: dict, consistencia_: float | None, casos: list[str]) -> str:
    """Relatório da avaliação (docs/avaliacao.md): o que mede, em quantos casos, e onde o sistema erra."""
    curto = {"COMPATIVEL": "Comp.", "PARCIAL": "Parc.", "INDETERMINADO": "Indet.", "INCOMPATIVEL": "Incomp.", "FORA_DO_PORTFOLIO": "Fora"}
    linhas = [
        "# Avaliação contra gabaritos",
        "",
        f"Gerado por `python eval/run_benchmark.py --markdown docs/avaliacao.md` · modo **{metricas['modo']}** · "
        f"{metricas['casos']} contratação(ões) com gabarito · {metricas.get('itens', 0)} itens · {metricas.get('pares', 0)} pares item × produto.",
        "",
        f"Casos: {', '.join(f'`{c}`' for c in casos)}.",
        "",
        "## Métricas-alvo",
        "",
        "| Métrica | Obtido |",
        "|---|---|",
        f"| Acerto por item | {_pct(metricas.get('acuracia_itens'))} |",
        f"| Precisão de COMPATÍVEL | {_pct(metricas.get('precisao_compativel'))} |",
        f"| Detecção de incompatibilidade | {_pct(metricas.get('deteccao_incompatibilidade'))} |",
        f"| Acerto nos pares item × produto | {_pct(metricas.get('acuracia_pares'))} |",
        f"| Citações conferidas (rastreabilidade) | {_pct(metricas.get('rastreabilidade'))} |",
        f"| Consistência entre execuções | {_pct(consistencia_) if consistencia_ is not None else '— (uma execução)'} |",
        "",
        "## Por classe",
        "",
        "| Classe | Precisão | Recall | Itens no gabarito |",
        "|---|---|---|---|",
        *[f"| {c} | {_pct(v['precisao'])} | {_pct(v['recall'])} | {v['suporte']} |" for c, v in classes.items()],
        "",
        "## Matriz de confusão",
        "",
        "Linha: o que o gabarito diz; coluna: o que o sistema respondeu.",
        "",
        "| Gabarito \\ Sistema | " + " | ".join(curto[c] for c in CLASSES) + " |",
        "|---|" + "---|" * len(CLASSES),
        *[f"| {curto[e]} | " + " | ".join(str(matriz[e][o]) for o in CLASSES) + " |" for e in CLASSES],
        "",
    ]
    return "\n".join(linhas)
