"""Planilha de rotulagem → gabarito.json de cada caso, com a concordância entre os dois revisores.

A planilha (separada por ";") tem uma linha por item: o que o sistema respondeu e o que cada revisor acha que é o
certo, sem ver o outro (revisor_1, revisor_2). Quando os dois concordam, o rótulo entra no gabarito; quando divergem,
vale a coluna `esperado`, preenchida depois de conversarem. O sistema nunca rotula: o gabarito só sai de pessoas.

Um caso só vira gabarito quando todos os itens dele estão resolvidos. O kappa de Cohen (concordância além do
acaso) vai para o relatório: abaixo de ~0,6, o critério de rotulagem precisa ser combinado de novo antes de medir.

Uso: python eval/gabarito_da_planilha.py docs/teste_cego_rotulagem.csv               # só mostra o andamento
     python eval/gabarito_da_planilha.py docs/teste_cego_rotulagem.csv --escrever    # grava os gabaritos prontos
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "eval"))

import metricas as m  # noqa: E402

COLUNAS = ("caso", "item", "revisor_1", "revisor_2", "esperado", "produto_esperado")


def ler(planilha: Path) -> list[dict[str, str]]:
    with open(planilha, encoding="utf-8-sig", newline="") as arq:
        linhas = list(csv.DictReader(arq, delimiter=";"))
    faltando = [c for c in COLUNAS if linhas and c not in linhas[0]]
    if faltando:
        raise ValueError(f"colunas ausentes na planilha: {', '.join(faltando)}")
    return linhas


def consolidar(linhas: list[dict[str, str]]) -> dict[str, dict]:
    """Por caso: itens resolvidos, pendentes (com o motivo) e os pares de rótulos dos dois revisores."""
    casos: dict[str, dict] = {}
    for n, linha in enumerate(linhas, start=2):  # linha 1 é o cabeçalho
        caso = casos.setdefault(linha["caso"], {"itens": {}, "pendentes": [], "revisores": []})
        try:
            r1, r2 = m.normalizar_rotulo(linha["revisor_1"]), m.normalizar_rotulo(linha["revisor_2"])
            consenso = m.normalizar_rotulo(linha["esperado"])
        except ValueError as exc:
            raise ValueError(f"linha {n}: {exc}") from exc
        item = str(int(linha["item"]))
        if r1 and r2:
            caso["revisores"].append((r1, r2))
        final = consenso or (r1 if r1 and r1 == r2 else None)
        if final is None:
            motivo = "falta um revisor" if not (r1 and r2) else f"divergência ({r1} × {r2}): preencha `esperado`"
            caso["pendentes"].append(f"item {item}: {motivo}")
            continue
        registro = {"esperado": final}
        if linha.get("produto_esperado", "").strip():
            registro["produto"] = linha["produto_esperado"].strip()
        caso["itens"][item] = registro
    return casos


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("planilha", type=Path)
    ap.add_argument("--escrever", action="store_true", help="grava data/casos/<caso>/gabarito.json dos casos completos")
    ap.add_argument("--sobrescrever", action="store_true", help="substitui um gabarito.json que já existe")
    args = ap.parse_args()

    casos = consolidar(ler(args.planilha))
    todos_os_pares = [p for c in casos.values() for p in c["revisores"]]
    print(f"{args.planilha}: {len(casos)} caso(s) · kappa geral {m.kappa(todos_os_pares) if todos_os_pares else '—'}\n")
    for nome, c in casos.items():
        total = len(c["itens"]) + len(c["pendentes"])
        concordes = sum(a == b for a, b in c["revisores"])
        k = m.kappa(c["revisores"])
        print(f"{nome}: {len(c['itens'])}/{total} itens resolvidos · revisores concordam em {concordes}/{len(c['revisores'])}"
              f" · kappa {k if k is not None else '—'}")
        for p in c["pendentes"][:5]:
            print(f"   pendente — {p}")
        if len(c["pendentes"]) > 5:
            print(f"   … e mais {len(c['pendentes']) - 5}")
        destino = RAIZ / "data" / "casos" / nome / "gabarito.json"
        if not args.escrever or c["pendentes"]:
            continue
        if not destino.parent.exists():
            print(f"   ✗ data/casos/{nome} não existe")
            continue
        if destino.exists() and not args.sobrescrever:
            print("   já tem gabarito.json (use --sobrescrever)")
            continue
        destino.write_text(json.dumps({
            "revisado_por": f"dois revisores independentes, divergências resolvidas em conjunto ({args.planilha.name}, {date.today():%d/%m/%Y};"
                            f" kappa {k})",
            "itens": c["itens"],
        }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"   ✓ gabarito gravado em {destino.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
