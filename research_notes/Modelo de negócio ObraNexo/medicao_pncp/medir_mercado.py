"""Mede no PNCP o nicho de material elétrico/iluminação em pregões eletrônicos (dado próprio para o BMC).

Fase A: lista todos os pregões eletrônicos publicados em duas janelas (últimos 30 dias e junho/2026) e
        classifica pelo OBJETO (palavras-chave de material elétrico/iluminação).
Fase B: para pregões de junho (já concluídos em sua maioria), baixa os itens de uma amostra e classifica
        cada ITEM com as regras de categoria do ObraNexo (inferir_categoria), medindo: fatia do valor em
        itens elétricos, situação dos itens (homologado/deserto/fracassado), benefício ME/EPP.
Fase C: amostra de pregões cujo objeto NÃO cita material elétrico, para medir a demanda "escondida".
Tudo fica em cache em disco: rodar de novo não repete consultas.
"""

from __future__ import annotations

import json
import random
import re
import statistics
import sys
import threading
import time
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from obranexo.connectors.pncp import BASE_CONSULTA, BASE_PNCP, PNCPClient, PNCPError
from obranexo.rules.extrair import inferir_categoria

sys.stdout.reconfigure(encoding="utf-8")
AQUI = Path(__file__).parent
CACHE = AQUI / "pncp_cache"
SAIDA = AQUI / "medicao_mercado.json"
random.seed(42)

JANELAS = {"30d": ("20260924", "20261023"), "jun": ("20260601", "20260630")}
AMOSTRA_ELETRICOS_JUN = 600
AMOSTRA_OUTROS_JUN = 400

_local = threading.local()


def cliente() -> PNCPClient:
    if not hasattr(_local, "c"):
        _local.c = PNCPClient(dir_cache=CACHE, pausa_s=0.35, offline=False)
    return _local.c


def norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


# Objeto que indica compra de material elétrico/iluminação
RE_OBJETO = re.compile(
    r"material(is)? eletric|eletric[oa]s? e (hidraul|de ilumin)|ilumina|luminari|\blampada|\bled\b|refletor|"
    r"disjunt|eletroduto|fios? e cabos|cabos? eletric|rele fotoel|poste(s)? (de|para) ilumin|subestac|transformador|"
    r"manutencao eletrica|instalac(ao|oes) eletric|quadro(s)? (de )?(distribuicao|comando)|infraestrutura eletric",
)
RE_EXCLUI_OBJETO = re.compile(r"veiculo eletric|bicicleta eletric|motocicleta eletric|carro eletric|onibus eletric")


def objeto_eletrico(objeto: str) -> bool:
    o = norm(objeto)
    return bool(RE_OBJETO.search(o)) and not RE_EXCLUI_OBJETO.search(o)


# Item elétrico: categoria das regras do ObraNexo, com filtros contra falsos positivos comuns
RE_CABO_ELETRICO = re.compile(r"eletric|flexiv|mm2|mm²|cobre|isola|750 ?v|0,6/1|kv|awg|pp |paralelo|multiplex|condutor|rigido")
RE_FALSO = re.compile(r"sutura|dental|vassoura|rodo|enxada|ferramenta|bisturi|cirurg|nylon|aco inox|odont|cateter|marcapasso")
CATEGORIAS_ELETRICAS = {"luminaria_publica_led", "luminaria_interna", "refletor_led", "lampada", "rele_fotoeletrico", "braco_luminaria",
                        "cabo", "disjuntor", "eletroduto", "quadro", "dispositivos", "transformador", "poste"}


def item_eletrico(descricao: str) -> str | None:
    d = norm(descricao)
    if RE_FALSO.search(d):
        return None
    cat = inferir_categoria(descricao)
    if cat not in CATEGORIAS_ELETRICAS:
        return None
    if cat == "cabo" and not RE_CABO_ELETRICO.search(d):
        return None
    if cat == "poste" and not re.search(r"ilumin|lumin|concreto|eletric|aco", d):
        return None
    return cat


def pagina(janela: str, n: int) -> tuple[list[dict], int, int]:
    ini, fim = JANELAS[janela]
    p = {"dataInicial": ini, "dataFinal": fim, "codigoModalidadeContratacao": 6, "pagina": n, "tamanhoPagina": 50}
    for tentativa in range(4):
        try:
            d = cliente().get_json(f"{BASE_CONSULTA}/contratacoes/publicacao", p)
            break
        except PNCPError:
            time.sleep(5 * (tentativa + 1))
    else:
        return [], 0, 0
    if not isinstance(d, dict):
        return [], 0, 0
    return d.get("data", []), int(d.get("totalPaginas") or 0), int(d.get("totalRegistros") or 0)


def listar(janela: str) -> list[dict]:
    _, total_pag, total_reg = pagina(janela, 1)
    print(f"[{janela}] {total_reg} pregões em {total_pag} páginas", flush=True)
    resultados: dict[int, list[dict]] = {}
    feitas = 0

    def tarefa(n: int):
        nonlocal feitas
        dados, _, _ = pagina(janela, n)
        resultados[n] = dados
        feitas += 1
        if feitas % 50 == 0:
            print(f"[{janela}] {feitas}/{total_pag} páginas", flush=True)

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(tarefa, range(1, total_pag + 1)))
    lista = []
    vistos = set()
    for n in sorted(resultados):
        for c in resultados[n]:
            cid = c.get("numeroControlePNCP")
            if cid and cid not in vistos:
                vistos.add(cid)
                lista.append(c)
    faltando = [n for n in range(1, total_pag + 1) if not resultados.get(n)]
    print(f"[{janela}] {len(lista)} pregões coletados; páginas vazias/falhas: {len(faltando)}", flush=True)
    return lista, total_reg, faltando


def resumo_objetos(lista: list[dict]) -> dict:
    el = [c for c in lista if objeto_eletrico(c.get("objetoCompra", ""))]
    valor = lambda cs: sum(float(c.get("valorTotalEstimado") or 0) for c in cs)
    ufs = Counter((c.get("unidadeOrgao") or {}).get("ufSigla") for c in el)
    esferas = Counter((c.get("orgaoEntidade") or {}).get("esferaId") for c in el)
    municipios = {((c.get("unidadeOrgao") or {}).get("codigoIbge")) for c in el}
    orgaos = {(c.get("orgaoEntidade") or {}).get("cnpj") for c in el}
    return {
        "pregoes_total": len(lista), "valor_total": round(valor(lista), 2),
        "pregoes_objeto_eletrico": len(el), "pct_pregoes": round(100 * len(el) / max(1, len(lista)), 2),
        "valor_objeto_eletrico": round(valor(el), 2), "pct_valor": round(100 * valor(el) / max(1, valor(lista)), 2),
        "orgaos_distintos": len(orgaos), "municipios_distintos": len(municipios),
        "por_uf": ufs.most_common(27), "por_esfera": dict(esferas),
        "GO": {"pregoes": ufs.get("GO", 0), "valor": round(valor([c for c in el if (c.get("unidadeOrgao") or {}).get("ufSigla") == "GO"]), 2)},
    }


def itens_de(c: dict) -> list[dict] | None:
    o = (c.get("orgaoEntidade") or {}).get("cnpj")
    try:
        d = cliente().get_json(f"{BASE_PNCP}/orgaos/{o}/compras/{c['anoCompra']}/{c['sequencialCompra']}/itens", {"pagina": 1, "tamanhoPagina": 500})
    except PNCPError:
        return None
    return d if isinstance(d, list) else None


SITUACAO = {1: "em_andamento", 2: "homologado", 3: "anulado_revogado", 4: "deserto", 5: "fracassado"}
BENEFICIO = {1: "exclusiva_me_epp", 2: "subcontratacao", 3: "cota_reservada", 4: "sem_beneficio", 5: "nao_se_aplica"}


def analisar_itens(amostra: list[dict], rotulo: str) -> dict:
    print(f"[itens:{rotulo}] baixando itens de {len(amostra)} pregões", flush=True)
    feitos = 0

    def tarefa(c):
        nonlocal feitos
        r = itens_de(c)
        feitos += 1
        if feitos % 50 == 0:
            print(f"[itens:{rotulo}] {feitos}/{len(amostra)}", flush=True)
        return c, r

    with ThreadPoolExecutor(max_workers=3) as pool:
        pares = list(pool.map(tarefa, amostra))
    ok = [(c, its) for c, its in pares if its]
    sit_el, sit_out, ben_el, cats = Counter(), Counter(), Counter(), Counter()
    valor_el = valor_tot = 0.0
    n_el_por_pregao, pregoes_com_el = [], 0
    for _, its in ok:
        n_el = 0
        for it in its:
            v = float(it.get("valorTotal") or 0)
            valor_tot += v
            cat = item_eletrico(it.get("descricao") or "") if it.get("materialOuServico") == "M" else None
            sit = SITUACAO.get(it.get("situacaoCompraItem"), "outra")
            if cat:
                n_el += 1
                valor_el += v
                cats[cat] += 1
                sit_el[sit] += 1
                ben_el[BENEFICIO.get(it.get("tipoBeneficio"), "outro")] += 1
            else:
                sit_out[sit] += 1
        if n_el:
            pregoes_com_el += 1
            n_el_por_pregao.append(n_el)

    def taxa_falha(s: Counter) -> float | None:
        concl = s["homologado"] + s["deserto"] + s["fracassado"]
        return round(100 * (s["deserto"] + s["fracassado"]) / concl, 2) if concl else None

    return {
        "pregoes_amostra": len(amostra), "pregoes_com_itens": len(ok),
        "pregoes_com_item_eletrico": pregoes_com_el, "pct_pregoes_com_item_eletrico": round(100 * pregoes_com_el / max(1, len(ok)), 2),
        "itens_eletricos": sum(sit_el.values()), "itens_outros": sum(sit_out.values()),
        "valor_itens_eletricos": round(valor_el, 2), "valor_itens_total": round(valor_tot, 2),
        "pct_valor_eletrico": round(100 * valor_el / max(1, valor_tot), 2),
        "itens_eletricos_por_pregao_mediana": statistics.median(n_el_por_pregao) if n_el_por_pregao else 0,
        "itens_eletricos_por_pregao_media": round(statistics.mean(n_el_por_pregao), 1) if n_el_por_pregao else 0,
        "situacao_itens_eletricos": dict(sit_el), "situacao_itens_outros": dict(sit_out),
        "taxa_deserto_fracassado_eletricos_pct": taxa_falha(sit_el), "taxa_deserto_fracassado_outros_pct": taxa_falha(sit_out),
        "beneficio_itens_eletricos": dict(ben_el), "categorias": cats.most_common(),
    }


def main():
    CACHE.mkdir(exist_ok=True)
    out: dict = {"metodo": __doc__, "janelas": JANELAS}
    t0 = time.time()
    listas = {}
    for j in JANELAS:
        lista, total_reg, faltando = listar(j)
        listas[j] = lista
        out[f"objetos_{j}"] = {**resumo_objetos(lista), "total_registros_pncp": total_reg, "paginas_falhas": len(faltando)}
        SAIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    jun = listas["jun"]
    el = [c for c in jun if objeto_eletrico(c.get("objetoCompra", ""))]
    outros = [c for c in jun if not objeto_eletrico(c.get("objetoCompra", ""))]
    am_el = random.sample(el, min(AMOSTRA_ELETRICOS_JUN, len(el)))
    am_out = random.sample(outros, min(AMOSTRA_OUTROS_JUN, len(outros)))
    out["itens_jun_objeto_eletrico"] = analisar_itens(am_el, "objeto_eletrico")
    SAIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    out["itens_jun_outros_objetos"] = analisar_itens(am_out, "outros")
    out["duracao_min"] = round((time.time() - t0) / 60, 1)
    SAIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("FIM", out["duracao_min"], "min", flush=True)


if __name__ == "__main__":
    main()
