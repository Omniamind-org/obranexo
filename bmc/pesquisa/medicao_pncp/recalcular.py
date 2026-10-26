"""Recalcula a medição só pelo cache: população completa de junho, medida estrita e ampla, extrapolação mensal/anual."""
import json
import random
import re
import sys
from collections import Counter

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
import medir_mercado as m  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
random.seed(42)

RE_ACESSORIO_ELETRICO = re.compile(
    r"^(cabinho|fita isolante|barramento|condulete|conector eletric|conector (de )?(perfuracao|derivacao|parafuso fendido)|"
    r"terminal (eletric|compressao|olhal|pino)|fusivel|caixa (de )?passagem|luva (de )?eletroduto|curva (de )?eletroduto|"
    r"canaleta|haste (de )?aterramento|reator|soquete|bocal|contator|dps|disjuntor|filtro de linha|rele fot|base (para )?rele|"
    r"chave (seccionadora|faca|boia)|isolador|mufla|emenda|plug|extensao eletric|sensor de presenca|minuteria)"
)


def eletrico_amplo(desc: str) -> bool:
    return bool(m.item_eletrico(desc)) or bool(RE_ACESSORIO_ELETRICO.search(m.norm(desc).strip()))


def medir(pregoes, rotulo):
    val_tot = val_est = val_amp = 0.0
    n_est = n_amp = com_el = com_el_amp = 0
    sit = Counter()
    ben = Counter()
    valor_cat = Counter()
    for c in pregoes:
        its = m.itens_de(c) or []
        tem = tem_amp = False
        for i in its:
            v = float(i.get("valorTotal") or 0)
            val_tot += v
            if i.get("materialOuServico") != "M":
                continue
            d = i.get("descricao") or ""
            cat = m.item_eletrico(d)
            amp = bool(cat) or bool(RE_ACESSORIO_ELETRICO.search(m.norm(d).strip()))
            if cat:
                n_est += 1
                val_est += v
                tem = True
                valor_cat[cat] += v
            if amp:
                n_amp += 1
                val_amp += v
                tem_amp = True
                sit[m.SITUACAO.get(i.get("situacaoCompraItem"), "outra")] += 1
                ben[m.BENEFICIO.get(i.get("tipoBeneficio"), "outro")] += 1
        com_el += tem
        com_el_amp += tem_amp
    concl = sit["homologado"] + sit["deserto"] + sit["fracassado"]
    return {
        "rotulo": rotulo, "pregoes": len(pregoes), "valor_itens": round(val_tot),
        "com_item_eletrico_estrito": com_el, "com_item_eletrico_amplo": com_el_amp,
        "itens_estrito": n_est, "itens_amplo": n_amp,
        "valor_estrito": round(val_est), "valor_amplo": round(val_amp),
        "situacao_amplo": dict(sit), "taxa_falha_amplo_pct": round(100 * (sit["deserto"] + sit["fracassado"]) / concl, 2) if concl else None,
        "anulado_revogado_pct": round(100 * sit["anulado_revogado"] / max(1, sum(sit.values())), 2),
        "beneficio_amplo": dict(ben), "valor_por_categoria_estrito": {k: round(v) for k, v in valor_cat.most_common()},
    }


jun, total_reg, falhas = m.listar("jun")
el = [c for c in jun if m.objeto_eletrico(c.get("objetoCompra", ""))]
outros = [c for c in jun if not m.objeto_eletrico(c.get("objetoCompra", ""))]
# A amostra original de "objeto elétrico" foi a população de então (530); os novos (das páginas que faltavam) têm itens fora do cache:
# mede só os que já têm itens em cache para não consultar o PNCP de novo.
am_el_orig = random.sample(el, min(m.AMOSTRA_ELETRICOS_JUN, len(el)))
r_el = medir(am_el_orig, "objeto_eletrico (amostra)")
random.seed(42)
_ = random.sample(el, min(m.AMOSTRA_ELETRICOS_JUN, len(el)))
am_out = random.sample(outros, min(m.AMOSTRA_OUTROS_JUN, len(outros)))
r_out = medir(am_out, "outros objetos (amostra)")

fator_el = len(el) / r_el["pregoes"]
fator_out = len(outros) / r_out["pregoes"]
mes = {
    "pregoes_jun_total": len(jun), "pregoes_jun_objeto_eletrico": len(el), "pregoes_jun_outros": len(outros),
    "fator_expansao_eletrico": round(fator_el, 3), "fator_expansao_outros": round(fator_out, 2),
}
for medida in ("estrito", "amplo"):
    v_el = r_el[f"valor_{medida}"] * fator_el
    v_out = r_out[f"valor_{medida}"] * fator_out
    p_el = r_el[f"com_item_eletrico_{medida}"] * fator_el
    p_out = r_out[f"com_item_eletrico_{medida}"] * fator_out
    mes[medida] = {
        "valor_mes_objeto_eletrico": round(v_el), "valor_mes_outros": round(v_out), "valor_mes_total": round(v_el + v_out),
        "valor_ano_x12": round(12 * (v_el + v_out)),
        "pregoes_mes_com_item_eletrico": round(p_el + p_out), "pregoes_mes_objeto_eletrico_com_item": round(p_el),
        "pregoes_mes_escondidos": round(p_out), "pct_escondidos": round(100 * p_out / max(1, p_el + p_out), 1),
    }
res = {"jun_total_registros": total_reg, "paginas_falhas": len(falhas), "amostra_eletrico": r_el, "amostra_outros": r_out, "extrapolacao_junho": mes}
(m.AQUI / "medicao_recalculada.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(res, ensure_ascii=False, indent=1))
