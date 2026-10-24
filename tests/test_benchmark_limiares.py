"""Trava de qualidade do CI: o benchmark falha quando uma métrica cai abaixo do mínimo."""

import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("run_benchmark", RAIZ / "eval" / "run_benchmark.py")
run_benchmark = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_benchmark)

LIMIARES = {"modo": "deterministico", "minimos": {"acuracia_itens": 1.0, "rastreabilidade": 0.95}}


def _metricas(**kw):
    base = {"acuracia_itens": 1.0, "rastreabilidade": 1.0, "chamadas_llm": 0, "modo": "deterministico", "casos": 2, "erros": []}
    return {**base, **kw}


def test_passa_quando_todas_as_metricas_atingem_o_minimo():
    assert run_benchmark.verificar_limiares(_metricas(rastreabilidade=0.95), LIMIARES) == []


def test_falha_quando_uma_metrica_cai():
    falhas = run_benchmark.verificar_limiares(_metricas(acuracia_itens=0.8889), LIMIARES)
    assert len(falhas) == 1 and "acuracia_itens" in falhas[0]


def test_falha_quando_nao_ha_dados_para_medir():
    falhas = run_benchmark.verificar_limiares(_metricas(rastreabilidade=None), LIMIARES)
    assert len(falhas) == 1 and "sem dados" in falhas[0]


def test_falha_quando_um_caso_da_erro():
    falhas = run_benchmark.verificar_limiares(_metricas(erros=["goianira: ValueError"]), LIMIARES)
    assert any("caso com erro" in f for f in falhas)


def test_falha_quando_roda_com_llm():
    falhas = run_benchmark.verificar_limiares(_metricas(modo="llm"), LIMIARES)
    assert any("modo llm" in f for f in falhas)


def test_limiares_do_repositorio_sao_validos():
    import json

    limiares = json.loads((RAIZ / "eval" / "limiares.json").read_text(encoding="utf-8"))
    assert limiares["modo"] == "deterministico"
    assert set(limiares["minimos"]) <= set(run_benchmark.METRICAS)
    assert all(0 < v <= 1 for v in limiares["minimos"].values())
