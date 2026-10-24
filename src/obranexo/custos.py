"""Custo de IA por análise: métrica INTERNA de margem e de cotas (não é informação para o cliente final).

O custo é estimado pelo ObraNexo: tokens que o provedor informa em cada chamada × tabela de preços de
`config.precos_usd`. Não é a fatura (nível gratuito, descontos de lote e câmbio podem diferir). Serve para
acompanhar o KPI do BMC — custo de IA abaixo de R$ 1 por análise e margem bruta de 75–85% — e, depois,
para orçamento por cliente. O cliente final vê cota de análises, não dólar.

Análises antigas, feitas quando o modelo ainda não tinha preço na tabela, têm custo registrado zero: o custo
é recalculado pelos tokens por modelo com o preço atual (sem descontos de cache, portanto um teto).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from obranexo.config import Config
from obranexo.models import Analise, Prospeccao, UsoLLM


def provedor_do_modelo(modelo: str) -> str:
    if modelo.startswith("gemini"):
        return "gemini"
    if modelo.startswith("claude"):
        return "anthropic"
    return "groq"


def _dinheiro(usd: float | None, cfg: Config) -> dict[str, float] | None:
    if usd is None:
        return None
    return {"usd": round(usd, 6), "brl": round(usd * cfg.cambio_brl, 4)}


def custo_por_modelo_usd(modelo: str, entrada: int, saida: int, cfg: Config) -> float | None:
    """Preço base da tabela; None quando o modelo não tem preço (o custo seria subestimado)."""
    preco = cfg.precos_usd.get(modelo)
    if preco is None:
        return None
    return (entrada * preco[0] + saida * preco[1]) / 1_000_000  # preco[2] é a leitura de cache, não usada no teto


def custo_do_uso(uso: UsoLLM, cfg: Config) -> tuple[float, str, list[str]]:
    """(custo em US$, origem, modelos sem preço). Origem: "registrado" (calculado em cada chamada, com
    cache e faixas), "recalculado" (registro zerado, refeito pelos tokens) ou "sem_ia"."""
    if uso.chamadas == 0:
        return 0.0, "sem_ia", []
    if uso.custo_usd > 0:
        return uso.custo_usd, "registrado", [m for m in uso.por_modelo if m not in cfg.precos_usd]
    total, sem_preco = 0.0, []
    for modelo, pm in uso.por_modelo.items():
        c = custo_por_modelo_usd(modelo, pm.get("entrada", 0), pm.get("saida", 0) + pm.get("raciocinio", 0), cfg)
        if c is None:
            sem_preco.append(modelo)
        else:
            total += c
    return total, "recalculado", sem_preco


def _estatisticas(valores: list[float], cfg: Config) -> dict[str, Any]:
    if not valores:
        return {"media": None, "mediana": None, "p95": None, "maximo": None}
    v = sorted(valores)
    meio = len(v) // 2
    mediana = v[meio] if len(v) % 2 else (v[meio - 1] + v[meio]) / 2
    p95 = v[min(len(v) - 1, max(0, -(-95 * len(v) // 100) - 1))]  # posição mais próxima (nearest-rank)
    return {k: _dinheiro(x, cfg) for k, x in {"media": sum(v) / len(v), "mediana": mediana, "p95": p95, "maximo": v[-1]}.items()}


def _no_periodo(quando, desde: date | None, ate: date | None) -> bool:
    dia = quando.date()
    return (desde is None or dia >= desde) and (ate is None or dia <= ate)


def resumo_custos(
    analises: list[Analise], prospeccoes: list[Prospeccao], cfg: Config, desde: date | None = None, ate: date | None = None, limite: int = 50
) -> dict[str, Any]:
    analises = [a for a in analises if _no_periodo(a.iniciada_em, desde, ate)]
    prospeccoes = [p for p in prospeccoes if _no_periodo(p.iniciada_em, desde, ate)]

    linhas, com_ia, sem_preco = [], [], set()
    por_dia: dict[str, dict[str, Any]] = defaultdict(lambda: {"analises": 0, "usd": 0.0})
    por_modelo: dict[str, dict[str, int]] = defaultdict(lambda: {"chamadas": 0, "entrada": 0, "saida": 0})
    for a in sorted(analises, key=lambda x: x.iniciada_em, reverse=True):
        usd, origem, faltam = custo_do_uso(a.uso_llm, cfg)
        sem_preco.update(faltam)
        if origem != "sem_ia":
            com_ia.append(usd)
        dia = por_dia[a.iniciada_em.date().isoformat()]
        dia["analises"] += 1
        dia["usd"] += usd
        for modelo, pm in a.uso_llm.por_modelo.items():
            for k in ("chamadas", "entrada", "saida"):
                por_modelo[modelo][k] += pm.get(k, 0)
        n_itens = len(a.itens)
        linhas.append({
            "id": a.id,
            "contratacao": a.contratacao.id,
            "orgao": a.contratacao.orgao_nome,
            "iniciada_em": a.iniciada_em.isoformat(),
            "status": a.status,
            "modo": a.modo,
            "itens": n_itens,
            "chamadas": a.uso_llm.chamadas,
            "tokens": {"entrada": a.uso_llm.tokens_entrada, "saida": a.uso_llm.tokens_saida, "cache_leitura": a.uso_llm.tokens_cache_leitura},
            "custo": _dinheiro(usd, cfg),
            "custo_por_item": _dinheiro(usd / n_itens, cfg) if n_itens and origem != "sem_ia" else None,
            "origem_custo": origem,
            "dentro_da_meta": None if origem == "sem_ia" else usd * cfg.cambio_brl <= cfg.meta_custo_analise_brl,
        })

    p_usd = 0.0
    p_uso = UsoLLM()
    for p in prospeccoes:
        usd, _, faltam = custo_do_uso(p.uso_llm, cfg)
        sem_preco.update(faltam)
        p_usd += usd
        p_uso.chamadas += p.uso_llm.chamadas
        p_uso.tokens_entrada += p.uso_llm.tokens_entrada
        p_uso.tokens_saida += p.uso_llm.tokens_saida
        for modelo, pm in p.uso_llm.por_modelo.items():
            for k in ("chamadas", "entrada", "saida"):
                por_modelo[modelo][k] += pm.get(k, 0)

    total_analises = sum(com_ia)
    meta_brl = cfg.meta_custo_analise_brl
    return {
        "aviso": "Métrica interna (margem e cotas). Estimativa: tokens × preço de tabela; não é a fatura do provedor e não deve ser exibida ao cliente final.",
        "periodo": {"desde": desde.isoformat() if desde else None, "ate": ate.isoformat() if ate else None},
        "moeda": {"cambio_brl": cfg.cambio_brl},
        "meta": {"custo_por_analise_brl": meta_brl,
                 "analises_dentro": sum(1 for x in com_ia if x * cfg.cambio_brl <= meta_brl),
                 "analises_com_ia": len(com_ia)},
        "analises": {
            "quantidade": len(analises),
            "com_ia": len(com_ia),
            "sem_ia": len(analises) - len(com_ia),
            "custo_total": _dinheiro(total_analises, cfg),
            "por_analise": _estatisticas(com_ia, cfg),
            "chamadas": sum(a.uso_llm.chamadas for a in analises),
            "tokens": {"entrada": sum(a.uso_llm.tokens_entrada for a in analises), "saida": sum(a.uso_llm.tokens_saida for a in analises)},
        },
        "prospeccoes": {
            "quantidade": len(prospeccoes),
            "custo_total": _dinheiro(p_usd, cfg),
            "chamadas": p_uso.chamadas,
            "tokens": {"entrada": p_uso.tokens_entrada, "saida": p_uso.tokens_saida},
        },
        "custo_total": _dinheiro(total_analises + p_usd, cfg),
        "por_modelo": [
            {
                "modelo": modelo,
                "provedor": provedor_do_modelo(modelo),
                "chamadas": pm["chamadas"],
                "tokens": {"entrada": pm["entrada"], "saida": pm["saida"]},
                "preco_tabela_usd_por_milhao": dict(zip(("entrada", "saida", "cache_leitura"), cfg.precos_usd[modelo], strict=True)) if modelo in cfg.precos_usd else None,
                "custo_estimado": _dinheiro(custo_por_modelo_usd(modelo, pm["entrada"], pm["saida"] + pm.get("raciocinio", 0), cfg), cfg),
            }
            for modelo, pm in sorted(por_modelo.items(), key=lambda kv: -kv[1]["entrada"] - kv[1]["saida"])
        ],
        "por_dia": [{"data": d, "analises": v["analises"], "custo": _dinheiro(v["usd"], cfg)} for d, v in sorted(por_dia.items())],
        "modelos_sem_preco": sorted(sem_preco),
        "analises_recentes": linhas[:limite],
    }
