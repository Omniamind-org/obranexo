from obranexo.catalog.loader import produto_de_dict
from obranexo.models import Operador, Requisito, ResultadoItem, ResultadoRequisito
from obranexo.rules.compare import comparar_item, comparar_requisito

PRODUTO = produto_de_dict(
    {
        "sku": "LPL-100", "nome": "Luminária 100 W", "categoria": "luminaria_publica_led",
        "atributos": {"potencia_w": 100, "tensao_v": [100, 277], "cct_k": 5000, "fluxo_lm": 14500, "eficiencia_lm_w": 145, "ip": "IP66",
                      "ik": "IK09", "garantia_anos": 5, "inmetro": True, "dimerizavel": False, "frequencia_hz": "50/60", "lente": "PMMA"},
        "certificacoes": ["INMETRO", "Curva fotométrica IES"],
    }
)


def req(atributo, operador, valor, obrigatorio=True, id="r1"):
    return Requisito(id=id, item_id="i", atributo=atributo, operador=Operador(operador), valor=valor, obrigatorio=obrigatorio)


def test_numero_igual_com_tolerancia():
    assert comparar_requisito(req("potencia_w", "=", 100), PRODUTO).resultado == ResultadoRequisito.ATENDE
    assert comparar_requisito(req("potencia_w", "=", 105), PRODUTO).resultado == ResultadoRequisito.ATENDE  # 10%
    assert comparar_requisito(req("potencia_w", "=", 150), PRODUTO).resultado == ResultadoRequisito.NAO_ATENDE


def test_maior_menor_igual():
    assert comparar_requisito(req("eficiencia_lm_w", ">=", 140), PRODUTO).resultado == ResultadoRequisito.ATENDE
    assert comparar_requisito(req("eficiencia_lm_w", ">=", 170), PRODUTO).resultado == ResultadoRequisito.NAO_ATENDE
    assert comparar_requisito(req("potencia_w", "<=", 100), PRODUTO).resultado == ResultadoRequisito.ATENDE
    assert comparar_requisito(req("potencia_w", "<=", 50), PRODUTO).resultado == ResultadoRequisito.NAO_ATENDE


def test_faixa_tensao_cobertura():
    assert comparar_requisito(req("tensao_v", "entre", [100, 277]), PRODUTO).resultado == ResultadoRequisito.ATENDE
    assert comparar_requisito(req("tensao_v", "entre", [90, 305]), PRODUTO).resultado == ResultadoRequisito.NAO_ATENDE
    assert comparar_requisito(req("tensao_v", "=", 220), PRODUTO).resultado == ResultadoRequisito.ATENDE
    assert comparar_requisito(req("tensao_v", "=", 380), PRODUTO).resultado == ResultadoRequisito.NAO_ATENDE


def test_enum_ordinal_ip_ik():
    assert comparar_requisito(req("ip", ">=", "IP65"), PRODUTO).resultado == ResultadoRequisito.ATENDE
    assert comparar_requisito(req("ip", ">=", "IP67"), PRODUTO).resultado == ResultadoRequisito.NAO_ATENDE
    assert comparar_requisito(req("ik", ">=", "IK08"), PRODUTO).resultado == ResultadoRequisito.ATENDE


def test_booleano_e_indeterminado():
    assert comparar_requisito(req("inmetro", "verdadeiro", True), PRODUTO).resultado == ResultadoRequisito.ATENDE
    assert comparar_requisito(req("dimerizavel", "verdadeiro", True), PRODUTO).resultado == ResultadoRequisito.NAO_ATENDE
    d = comparar_requisito(req("dps_ka", ">=", 10), PRODUTO)
    assert d.resultado == ResultadoRequisito.INDETERMINADO and "não informa" in d.justificativa


def test_texto_e_documental():
    assert comparar_requisito(req("lente", "contem", "pmma"), PRODUTO).resultado == ResultadoRequisito.ATENDE
    assert comparar_requisito(req("frequencia_hz", "contem", "50/60"), PRODUTO).resultado == ResultadoRequisito.ATENDE
    assert comparar_requisito(req("doc_curva_ies", "contem", True), PRODUTO).resultado == ResultadoRequisito.ATENDE
    assert comparar_requisito(req("doc_ensaios", "contem", True), PRODUTO).resultado == ResultadoRequisito.NAO_ATENDE


def test_texto_com_medidas_em_redacao_diferente():
    p = produto_de_dict({"sku": "X", "nome": "X", "categoria": "c", "atributos": {"fixacao": "encaixe para braço 33 a 60,3 mm, ajuste 0-15°"}})
    assert comparar_requisito(req("fixacao", "contem", "tubo 33 à Ø 60,3mm"), p).resultado == ResultadoRequisito.ATENDE
    assert comparar_requisito(req("fixacao", "contem", "tubo 48 à Ø 76mm"), p).resultado == ResultadoRequisito.NAO_ATENDE


def test_agregacao():
    reqs = [req("potencia_w", "=", 100, id="a"), req("ip", ">=", "IP66", id="b"), req("lente", "contem", "vidro", obrigatorio=False, id="c")]
    resultado, score, _ = comparar_item(reqs, PRODUTO)
    assert resultado == ResultadoItem.PARCIAL and 0 < score < 1
    reqs.append(req("dimerizavel", "verdadeiro", True, id="d"))
    assert comparar_item(reqs, PRODUTO)[0] == ResultadoItem.INCOMPATIVEL
    reqs = [req("potencia_w", "=", 100, id="a"), req("dps_ka", ">=", 10, id="e")]
    assert comparar_item(reqs, PRODUTO)[0] == ResultadoItem.INDETERMINADO
    reqs = [req("potencia_w", "=", 100, id="a"), req("ip", ">=", "IP66", id="b")]
    assert comparar_item(reqs, PRODUTO)[0] == ResultadoItem.COMPATIVEL
