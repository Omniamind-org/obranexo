"""Validação dos valores propostos pelo LLM — exemplos reais do teste cego com o Gemini (23/10/2026)."""

import pytest

from obranexo.catalog.loader import produto_de_dict
from obranexo.models import Operador, Requisito, ResultadoRequisito
from obranexo.rules.compare import comparar_requisito_seguro
from obranexo.rules.validar import normalizar_valor


@pytest.mark.parametrize(
    ("atributo", "bruto", "esperado"),
    [
        ("cct_k", "branca fria", None),  # derrubava a análise inteira
        ("cct_k", "6.500", 6500.0),
        ("cct_k", [4000, 5000], [4000.0, 5000.0]),
        ("tensao_v", [600, 1000], None),  # 0,6/1 kV é tensão de isolação de cabo
        ("tensao_v", "127-277V", [127.0, 277.0]),
        ("tensao_v", "127 - 277 V", [127.0, 277.0]),
        ("temp_operacao_c", "-10 a +40", [-10.0, 40.0]),
        ("temp_operacao_c", "de -20 a 50 °C", [-20.0, 50.0]),
        ("tensao_v", 220, 220.0),
        ("material_corpo", "PRETA", None),  # cor, não material
        ("material_corpo", "alumínio injetado", "alumínio injetado"),
        ("tipo_cabo", "CABO DE COBRE, FLEXIVEL, CLASSE 4 OU 5", None),  # texto livre, não é um tipo válido
        ("tipo_cabo", "cabo fotovoltaico", "fotovoltaico"),
        ("ip", 66, "IP66"),
        ("ip", "IP 67", "IP67"),
        ("ip", "alto", None),
        ("garantia_anos", "60 meses", 5.0),
        ("garantia_anos", 50, None),
        ("doc_amostra", 15, True),  # o "15" era prazo de entrega da amostra
        ("inmetro", "sim", True),
        ("fator_potencia", 0.92, 0.92),
        ("fator_potencia", 92, None),
        ("atributo_inventado", 1, None),
    ],
)
def test_normalizar_valor(atributo, bruto, esperado):
    valor, motivo = normalizar_valor(atributo, bruto)
    assert valor == esperado, motivo
    if esperado is None:
        assert motivo


def test_comparacao_nunca_derruba_a_analise():
    produto = produto_de_dict({"sku": "X", "nome": "X", "categoria": "c", "atributos": {"cct_k": 5000}})
    req = Requisito(id="r", item_id="i", atributo="cct_k", operador=Operador.IGUAL, valor="branca fria")
    d = comparar_requisito_seguro(req, produto)
    assert d.resultado == ResultadoRequisito.INDETERMINADO and "não interpretável" in d.justificativa
