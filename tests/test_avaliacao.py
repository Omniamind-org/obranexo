"""Métricas da avaliação (eval/metricas.py) e a planilha de rotulagem → gabarito (eval/gabarito_da_planilha.py)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "eval"))
import metricas as m  # noqa: E402

_spec = importlib.util.spec_from_file_location("gabarito_da_planilha", RAIZ / "eval" / "gabarito_da_planilha.py")
planilha = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(planilha)


@pytest.mark.parametrize("rotulo, classe", [("Compatível", "COMPATIVEL"), ("fora", "FORA_DO_PORTFOLIO"), (" incompatível ", "INCOMPATIVEL"), ("", None)])
def test_rotulos_da_planilha(rotulo, classe):
    assert m.normalizar_rotulo(rotulo) == classe


def test_rotulo_desconhecido_e_recusado():
    with pytest.raises(ValueError, match="rótulo desconhecido"):
        m.normalizar_rotulo("talvez")


def test_kappa():
    # concordância observada 0,75; esperada por acaso 0,5 → kappa 0,5
    assert m.kappa([("COMPATIVEL", "COMPATIVEL")] * 2 + [("PARCIAL", "PARCIAL"), ("COMPATIVEL", "PARCIAL")]) == 0.5
    assert m.kappa([("PARCIAL", "PARCIAL")] * 3) == 1.0
    assert m.kappa([]) is None


def test_matriz_precisao_e_recall():
    matriz = m.matriz_confusao([("COMPATIVEL", "COMPATIVEL"), ("COMPATIVEL", "PARCIAL"), ("INCOMPATIVEL", "COMPATIVEL")])
    classes = m.por_classe(matriz)
    assert matriz["COMPATIVEL"]["PARCIAL"] == 1
    assert classes["COMPATIVEL"] == {"precisao": 0.5, "recall": 0.5, "suporte": 2}
    assert classes["INDETERMINADO"] == {"precisao": None, "recall": None, "suporte": 0}


def test_consistencia_entre_execucoes():
    assert m.consistencia([{"c/1": "COMPATIVEL", "c/2": "PARCIAL"}, {"c/1": "COMPATIVEL", "c/2": "INDETERMINADO"}]) == 0.5
    assert m.consistencia([{"c/1": "COMPATIVEL"}]) is None


def test_planilha_vira_gabarito_so_com_os_dois_revisores(tmp_path):
    csv = tmp_path / "rotulagem.csv"
    csv.write_text(
        "caso;item;resultado_sistema;revisor_1;revisor_2;esperado;produto_esperado;observacao\n"
        "a;1;COMPATIVEL;Compatível;Compatível;;LPL-100;\n"      # concordam: entra
        "a;2;PARCIAL;Parcial;Incompatível;Incompatível;;\n"     # divergem, resolvido no esperado
        "b;1;FORA;Fora;Compatível;;;\n"                         # divergem sem resolver: pendente
        "b;2;FORA;Fora;;;;\n",                                  # falta um revisor: pendente
        encoding="utf-8",
    )
    casos = planilha.consolidar(planilha.ler(csv))
    assert casos["a"]["itens"] == {"1": {"esperado": "COMPATIVEL", "produto": "LPL-100"}, "2": {"esperado": "INCOMPATIVEL"}}
    assert casos["a"]["pendentes"] == []
    assert casos["b"]["itens"] == {}
    assert [p.split(":")[0] for p in casos["b"]["pendentes"]] == ["item 1", "item 2"]
    assert len(casos["a"]["revisores"]) == 2 and len(casos["b"]["revisores"]) == 1  # o kappa só usa itens com os dois


def test_a_planilha_do_teste_cego_tem_o_formato_esperado():
    casos = planilha.consolidar(planilha.ler(RAIZ / "docs" / "teste_cego_rotulagem.csv"))
    assert sum(len(c["itens"]) + len(c["pendentes"]) for c in casos.values()) == 133
