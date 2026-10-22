"""Benchmark do ObraNexo contra gabaritos revisados manualmente.

Cada caso em data/casos/<caso>/gabarito.json tem o formato:
{
  "itens": {"1": {"esperado": "COMPATIVEL", "produto": "LPL-100-50K"}, ...},
  "pares": [{"item": 3, "produto": "LPL-50-50K-ECO", "esperado": "INCOMPATIVEL", "motivo": "..."}]
}
Métricas (seção 13 do roadmap): acurácia por item, precisão de COMPATÍVEL, detecção de
incompatibilidades, rastreabilidade (evidências verificadas), tempo e custo.

Uso: python eval/run_benchmark.py [--casos goianira_pe038_2026 aruana_pp005_2026] [--catalogo ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from obranexo.agents.pipeline import executar_caso  # noqa: E402
from obranexo.catalog.loader import carregar_catalogo_json  # noqa: E402
from obranexo.config import config  # noqa: E402
from obranexo.connectors.pncp import listar_casos  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--casos", nargs="*")
    ap.add_argument("--catalogo", default=str(config.catalogo_demo))
    ap.add_argument("--saida", default=str(RAIZ / "docs" / "benchmark_resultado.json"))
    args = ap.parse_args()

    empresa = carregar_catalogo_json(Path(args.catalogo))
    casos = [config.dir_casos / c for c in args.casos] if args.casos else [d for d in listar_casos() if (d / "gabarito.json").exists()]
    if not casos:
        print("nenhum caso com gabarito.json")
        return 1

    tot = {"itens": 0, "itens_ok": 0, "compat_previstos": 0, "compat_corretos": 0, "incompat_esperados": 0, "incompat_detectados": 0,
           "pares": 0, "pares_ok": 0, "evidencias": 0, "evidencias_ok": 0, "tempo_s": 0.0, "custo_usd": 0.0, "chamadas_llm": 0}
    relatorio = []
    for caso in casos:
        gabarito = json.loads((caso / "gabarito.json").read_text(encoding="utf-8"))
        analise = executar_caso(caso, empresa, salvar=False)
        if analise.status != "concluida":
            print(f"{caso.name}: ERRO {analise.erro}")
            continue
        skus = {p.id: p.sku for p in empresa.produtos}
        melhor: dict[int, tuple[str, str]] = {}
        ordem = {"COMPATIVEL": 3, "PARCIAL": 2, "INDETERMINADO": 1, "INCOMPATIVEL": 0}
        for c in sorted(analise.correspondencias, key=lambda c: (ordem[c.resultado.value], c.score), reverse=True):
            n = analise.item(c.item_id).numero_item
            melhor.setdefault(n, (c.resultado.value, skus.get(c.produto_id, c.produto_id)))
        linhas = []
        for num, esperado in gabarito.get("itens", {}).items():
            obtido = melhor.get(int(num), ("FORA_DO_PORTFOLIO", "—"))
            ok = obtido[0] == esperado["esperado"] and (not esperado.get("produto") or esperado["produto"] == obtido[1])
            tot["itens"] += 1
            tot["itens_ok"] += int(ok)
            if obtido[0] == "COMPATIVEL":
                tot["compat_previstos"] += 1
                tot["compat_corretos"] += int(esperado["esperado"] == "COMPATIVEL")
            if esperado["esperado"] == "INCOMPATIVEL":
                tot["incompat_esperados"] += 1
                tot["incompat_detectados"] += int(obtido[0] == "INCOMPATIVEL")
            linhas.append({"item": int(num), "esperado": esperado, "obtido": {"resultado": obtido[0], "produto": obtido[1]}, "ok": ok})
        pares = []
        for par in gabarito.get("pares", []):
            item = next((i for i in analise.itens if i.numero_item == par["item"]), None)
            prod_id = next((p.id for p in empresa.produtos if p.sku == par["produto"]), None)
            corr = next((c for c in analise.correspondencias if item and c.item_id == item.id and c.produto_id == prod_id), None)
            if corr is None:  # fora do top-N: recomputa diretamente
                from obranexo.rules.compare import comparar_item

                reqs = [r for r in analise.requisitos if item and r.item_id == item.id]
                prod = next(p for p in empresa.produtos if p.id == prod_id)
                obtido = comparar_item(reqs, prod)[0].value
            else:
                obtido = corr.resultado.value
            ok = obtido == par["esperado"]
            tot["pares"] += 1
            tot["pares_ok"] += int(ok)
            pares.append({**par, "obtido": obtido, "ok": ok})
        ev_ok = sum(e.verificada for e in analise.evidencias)
        tot["evidencias"] += len(analise.evidencias)
        tot["evidencias_ok"] += ev_ok
        tot["tempo_s"] += analise.duracao_s() or 0
        tot["custo_usd"] += analise.uso_llm.custo_usd
        tot["chamadas_llm"] += analise.uso_llm.chamadas
        relatorio.append({"caso": caso.name, "contratacao": analise.contratacao.id, "modo": analise.modo, "tempo_s": round(analise.duracao_s() or 0, 1),
                          "custo_usd": analise.uso_llm.custo_usd, "evidencias": f"{ev_ok}/{len(analise.evidencias)}", "itens": linhas, "pares": pares})
        print(
            f"{caso.name}: itens {sum(ln['ok'] for ln in linhas)}/{len(linhas)} · pares {sum(p['ok'] for p in pares)}/{len(pares)} · "
            f"evidências {ev_ok}/{len(analise.evidencias)} · {analise.duracao_s():.1f}s · US$ {analise.uso_llm.custo_usd:.4f}"
        )
        for ln in linhas:
            if not ln["ok"]:
                print(f"   ✗ item {ln['item']}: esperado {ln['esperado']} obtido {ln['obtido']}")
        for p in pares:
            if not p["ok"]:
                print(f"   ✗ par item {p['item']} × {p['produto']}: esperado {p['esperado']} obtido {p['obtido']}")

    def pct(a, b):
        return f"{(a / b * 100):.0f}%" if b else "n/a"

    resumo = {
        "acuracia_itens": pct(tot["itens_ok"], tot["itens"]),
        "precisao_compativel": pct(tot["compat_corretos"], tot["compat_previstos"]),
        "deteccao_incompatibilidade": pct(tot["incompat_detectados"], tot["incompat_esperados"]),
        "acuracia_pares": pct(tot["pares_ok"], tot["pares"]),
        "rastreabilidade": pct(tot["evidencias_ok"], tot["evidencias"]),
        "tempo_total_s": round(tot["tempo_s"], 1),
        "custo_total_usd": round(tot["custo_usd"], 4),
        "chamadas_llm": tot["chamadas_llm"],
        "modo": "llm" if config.llm_disponivel else "deterministico",
    }
    print("\nRESUMO:", json.dumps(resumo, ensure_ascii=False, indent=1))
    Path(args.saida).write_text(json.dumps({"resumo": resumo, "casos": relatorio}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"Relatório salvo em {args.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
