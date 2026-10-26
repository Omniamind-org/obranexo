"""Inspeciona, só pelo cache, por que tantos pregões de objeto elétrico não têm itens elétricos reconhecidos."""
import random
import sys
from collections import Counter

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import medir_mercado as m  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
random.seed(42)
jun, _, _ = m.listar("jun")
el = [c for c in jun if m.objeto_eletrico(c.get("objetoCompra", ""))]
am = random.sample(el, min(m.AMOSTRA_ELETRICOS_JUN, len(el)))
sem, servicos, desc_nao = [], 0, Counter()
for c in am:
    its = m.itens_de(c) or []
    n_el = sum(1 for i in its if i.get("materialOuServico") == "M" and m.item_eletrico(i.get("descricao") or ""))
    if not n_el:
        so_serv = its and all(i.get("materialOuServico") == "S" for i in its)
        servicos += bool(so_serv)
        sem.append((c["objetoCompra"][:110], len(its), "SERVIÇO" if so_serv else ""))
    else:
        for i in its:
            if i.get("materialOuServico") == "M" and not m.item_eletrico(i.get("descricao") or ""):
                desc_nao[m.norm(i.get("descricao") or "")[:40]] += 1
print(f"sem item elétrico: {len(sem)} de {len(am)}; destes, só serviços: {servicos}")
for o in random.sample(sem, 25):
    print(" -", o)
print("\nitens de material NÃO reconhecidos (em pregões que têm elétricos), mais comuns:")
for d, n in desc_nao.most_common(40):
    print(f"  {n:4} {d}")
