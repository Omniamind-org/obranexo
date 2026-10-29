"""Benchmark do ObraNexo contra gabaritos revisados manualmente.

Cada caso em data/casos/<caso>/gabarito.json tem o formato:
{
  "itens": {"1": {"esperado": "COMPATIVEL", "produto": "LPL-100-50K"}, ...},
  "pares": [{"item": 3, "produto": "LPL-50-50K-ECO", "esperado": "INCOMPATIVEL", "motivo": "..."}]
}
Métricas (seção 13 do roadmap): acurácia por item, precisão de COMPATÍVEL, detecção de
incompatibilidades, rastreabilidade (evidências verificadas), tempo e custo; precisão e recall por classe,
matriz de confusão e consistência entre execuções (eval/metricas.py).

Uso: python eval/run_benchmark.py [--casos goianira_pe038_2026 aruana_pp005_2026] [--catalogo ...]
     python eval/run_benchmark.py --limiares eval/limiares.json   # trava do CI: sai com código 1 se cair
     python eval/run_benchmark.py --repeticoes 3 --markdown docs/avaliacao.md   # relatório com consistência
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "eval"))

import metricas as m  # noqa: E402
from obranexo.agents.pipeline import executar_caso  # noqa: E402
from obranexo.catalog.loader import carregar_catalogo_json  # noqa: E402
from obranexo.config import config  # noqa: E402
from obranexo.connectors.pncp import listar_casos  # noqa: E402

METRICAS = {
    "acuracia_itens": "Acerto por item",
    "precisao_compativel": "Precisão de COMPATÍVEL",
    "deteccao_incompatibilidade": "Detecção de incompatibilidade",
    "acuracia_pares": "Acerto nos pares item × produto",
    "rastreabilidade": "Citações conferidas",
}


def verificar_limiares(metricas: dict, limiares: dict) -> list[str]:
    """Compara as métricas com os mínimos; devolve as falhas (lista vazia = passou)."""
    falhas = [f"caso com erro: {e}" for e in metricas["erros"]]
    modo = limiares.get("modo")
    if modo and metricas["modo"] != modo:
        falhas.append(f"o benchmark rodou em modo {metricas['modo']}; a trava exige {modo} (OBRANEXO_LLM_PROVIDER=none)")
    for nome, minimo in limiares.get("minimos", {}).items():
        valor = metricas.get(nome)
        if valor is None:
            falhas.append(f"{nome}: sem dados para medir (mínimo {minimo:.0%})")
        elif valor < minimo:
            falhas.append(f"{nome}: {valor:.1%} abaixo do mínimo de {minimo:.0%}")
    return falhas


def _publicar_resumo_github(metricas: dict, limiares: dict, falhas: list[str]) -> None:
    """No GitHub Actions, escreve a tabela das métricas no resumo da execução."""
    destino = os.environ.get("GITHUB_STEP_SUMMARY")
    if not destino:
        return
    linhas = ["### Benchmark contra gabaritos", "", "| Métrica | Obtido | Mínimo | |", "|---|---|---|---|"]
    for nome, minimo in limiares.get("minimos", {}).items():
        valor = metricas.get(nome)
        ok = valor is not None and valor >= minimo
        linhas.append(f"| {METRICAS.get(nome, nome)} | {'—' if valor is None else f'{valor:.1%}'} | {minimo:.0%} | {'✅' if ok else '❌'} |")
    linhas += ["", f"Modo: {metricas['modo']} · casos: {metricas['casos']} · chamadas ao LLM: {metricas['chamadas_llm']}", ""]
    linhas += ["**Passou.**"] if not falhas else ["**Falhou:**", *[f"- {f}" for f in falhas]]
    with open(destino, "a", encoding="utf-8") as arq:
        arq.write("\n".join(linhas) + "\n")


def _melhor_por_item(analise, skus: dict[str, str]) -> dict[int, tuple[str, str]]:
    """O melhor resultado de cada item (o que o dossiê mostra) e o SKU do produto."""
    ordem = {"COMPATIVEL": 3, "PARCIAL": 2, "INDETERMINADO": 1, "INCOMPATIVEL": 0}
    melhor: dict[int, tuple[str, str]] = {}
    for c in sorted(analise.correspondencias, key=lambda c: (ordem[c.resultado.value], c.score), reverse=True):
        melhor.setdefault(analise.item(c.item_id).numero_item, (c.resultado.value, skus.get(c.produto_id, c.produto_id)))
    return melhor


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--casos", nargs="*")
    ap.add_argument("--catalogo", default=str(config.catalogo_demo))
    ap.add_argument("--saida", default=str(RAIZ / "docs" / "benchmark_resultado.json"))
    ap.add_argument("--limiares", help="JSON com os mínimos por métrica; abaixo deles o comando sai com código 1 (trava do CI)")
    ap.add_argument("--repeticoes", type=int, default=1, help="executa cada caso N vezes para medir a consistência (com LLM, N chamadas)")
    ap.add_argument("--markdown", help="também escreve o relatório em Markdown (ex.: docs/avaliacao.md)")
    args = ap.parse_args()

    empresa = carregar_catalogo_json(Path(args.catalogo))
    casos = [config.dir_casos / c for c in args.casos] if args.casos else [d for d in listar_casos() if (d / "gabarito.json").exists()]
    if not casos:
        print("nenhum caso com gabarito.json")
        return 1

    tot = {"itens": 0, "itens_ok": 0, "compat_previstos": 0, "compat_corretos": 0, "incompat_esperados": 0, "incompat_detectados": 0,
           "pares": 0, "pares_ok": 0, "evidencias": 0, "evidencias_ok": 0, "tempo_s": 0.0, "custo_usd": 0.0, "chamadas_llm": 0}
    relatorio = []
    erros: list[str] = []
    classificados: list[tuple[str, str]] = []  # (esperado, obtido) por item, para a matriz de confusão
    execucoes: list[dict[str, str]] = [{} for _ in range(max(1, args.repeticoes))]
    skus = {p.id: p.sku for p in empresa.produtos}
    for caso in casos:
        gabarito = json.loads((caso / "gabarito.json").read_text(encoding="utf-8"))
        rodadas = [executar_caso(caso, empresa, salvar=False) for _ in range(max(1, args.repeticoes))]
        analise = rodadas[0]
        if any(a.status != "concluida" for a in rodadas):
            falha = next(a for a in rodadas if a.status != "concluida")
            print(f"{caso.name}: ERRO {falha.erro}")
            erros.append(f"{caso.name}: {falha.erro}")
            continue
        for i, rodada in enumerate(rodadas):
            for num, (resultado, _) in _melhor_por_item(rodada, skus).items():
                execucoes[i][f"{caso.name}/{num}"] = resultado
        melhor = _melhor_por_item(analise, skus)
        linhas = []
        for num, esperado in gabarito.get("itens", {}).items():
            obtido = melhor.get(int(num), ("FORA_DO_PORTFOLIO", "—"))
            classificados.append((m.normalizar_rotulo(esperado["esperado"]), obtido[0]))
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
    def razao(a, b):
        return round(a / b, 4) if b else None

    metricas = {
        "acuracia_itens": razao(tot["itens_ok"], tot["itens"]),
        "precisao_compativel": razao(tot["compat_corretos"], tot["compat_previstos"]),
        "deteccao_incompatibilidade": razao(tot["incompat_detectados"], tot["incompat_esperados"]),
        "acuracia_pares": razao(tot["pares_ok"], tot["pares"]),
        "rastreabilidade": razao(tot["evidencias_ok"], tot["evidencias"]),
        "chamadas_llm": tot["chamadas_llm"],
        "modo": resumo["modo"],
        "casos": len(casos),
        "itens": tot["itens"],
        "pares": tot["pares"],
        "erros": erros,
    }
    matriz = m.matriz_confusao(classificados)
    classes = m.por_classe(matriz)
    consistencia = m.consistencia(execucoes)
    print("\nRESUMO:", json.dumps(resumo, ensure_ascii=False, indent=1))
    Path(args.saida).write_text(
        json.dumps({"resumo": resumo, "metricas": metricas, "por_classe": classes, "matriz_confusao": matriz, "consistencia": consistencia,
                    "casos": relatorio}, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    print(f"Relatório salvo em {args.saida}")
    if args.markdown:
        Path(args.markdown).write_text(m.markdown(metricas, matriz, classes, consistencia, [c.name for c in casos]), encoding="utf-8")
        print(f"Relatório em Markdown salvo em {args.markdown}")

    if not args.limiares:
        return 0
    limiares = json.loads(Path(args.limiares).read_text(encoding="utf-8"))
    falhas = verificar_limiares(metricas, limiares)
    _publicar_resumo_github(metricas, limiares, falhas)
    if falhas:
        print("\nTRAVA DE QUALIDADE: FALHOU")
        for f in falhas:
            print(f"  ✗ {f}")
        return 1
    print("\nTRAVA DE QUALIDADE: passou (todas as métricas nos mínimos de " + args.limiares + ")")
    return 0


if __name__ == "__main__":
    sys.exit(main())
