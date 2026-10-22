from obranexo.models import Operador
from obranexo.rules.extrair import extrair_requisitos, inferir_categoria, numero_br

GOIANIRA_100W = (
    "LUMINÁRIA PÚBLICA LED 100 WTS, POTÊNCIA 100 WTS, COR 5000K LUZ BRANCA FRIA, TENSÃO DE OPERAÇÃO AUTOVOLT (100V-277) "
    "CONNFECIONADA EM ALUMÍNIO, COM DISSIPADOR DE CALOR EM ALUMÍNIO, LENTE EM PMMA, FREQUÊNCIA NOMINAL 50/60HZ, "
    "EFICIÊNCIA LUMINOSA 140LM/WATT, FLUXO LUMINOSO 14000 LM, ÂNGULO DE ABERTURA 70X140, FATOR DE POTÊNCIA 0,98,IRC 70, "
    "LED TIPO SMD, TEMPERATURA DE FUNCIONAMENTO 5C A + 50C, ÍNDICE DE PROTEÇÃO IP 66, VIDA ÚTIL 50,000 HORAS, "
    "TOMADA PARA RELE FOTOELÉTRICO SIM ,GRAU DE IMPACTO IK 08, CLASSE DE EQUIPAMENTO CLASSE 1, ILUMINAÇÃO DIMERIZÁVEL, "
    "LUMINÁRIA COM ARTICULAÇÃO PARA ENCAIXE BRAÇO VÁRIOS ÂNGULOS, SELO INMETRO, 05 ANOS DE GARANTIA COM REGISTRO DE FABRICA. "
    "OBRIGATÓRIO APRESENTAÇÃO DO TERMO DE GARANTIA, REGISTRO DE INMETRO, ENSAIOS E CURVA FOTOMÉTRICA IES."
)

ARUANA_50W = (
    "Luminária para iluminação pública a LED potência máxima de 50W, com as seguintes características: confeccionada em liga de "
    "alumínio injetado a alta pressão ou extrusão, lente em policarbonato e refrator em vidro plano, grau de proteção mínimo do "
    "conjunto IP-66, resistente a impacto mecânico IK-08. Temperatura de cor 5000K. Potência máxima de 50W, Eficiência Luminosa "
    "mínima de 170 lm/W com fluxo luminoso efetivo de 8.500 lumens ; índice de reprodução de cor 70 ou maior; alimentação 127- 277V "
    "ou faixa de variação superior, frequência 50 ou 60Hz, fator de potência mínimo (0,92), possuir DPS de no mínimo 10KA"
)


def _por_atributo(descricao):
    return {r.atributo: r for r in extrair_requisitos(descricao)}


def test_numero_br():
    assert numero_br("8.500") == 8500
    assert numero_br("50,000") == 50000
    assert numero_br("0,98") == 0.98
    assert numero_br("14000") == 14000
    assert numero_br("1.671,18") == 1671.18


def test_goianira_extracao_completa():
    r = _por_atributo(GOIANIRA_100W)
    assert r["potencia_w"].valor == 100 and r["potencia_w"].operador == Operador.IGUAL
    assert r["tensao_v"].valor == [100.0, 277.0] and r["tensao_v"].operador == Operador.ENTRE
    assert r["cct_k"].valor == 5000
    assert r["fluxo_lm"].valor == 14000 and r["fluxo_lm"].operador == Operador.MAIOR_IGUAL
    assert r["eficiencia_lm_w"].valor == 140
    assert r["irc"].valor == 70
    assert r["fator_potencia"].valor == 0.98
    assert r["ip"].valor == "IP66" and r["ik"].valor == "IK08"
    assert r["vida_util_h"].valor == 50000
    assert r["garantia_anos"].valor == 5
    assert r["inmetro"].valor is True and r["dimerizavel"].valor is True and r["tomada_rele"].valor is True
    assert r["lente"].valor == "pmma" and r["lente"].obrigatorio is False
    assert r["led_tipo"].valor == "SMD"
    assert "doc_termo_garantia" in r and "doc_curva_ies" in r and "doc_ensaios" in r
    for req in r.values():
        assert req.texto_origem and req.texto_origem in GOIANIRA_100W


def test_aruana_operadores_por_contexto():
    r = _por_atributo(ARUANA_50W)
    assert r["potencia_w"].operador == Operador.MENOR_IGUAL and r["potencia_w"].valor == 50
    assert r["eficiencia_lm_w"].operador == Operador.MAIOR_IGUAL and r["eficiencia_lm_w"].valor == 170
    assert r["fluxo_lm"].valor == 8500
    assert r["tensao_v"].valor == [127.0, 277.0]
    assert r["fator_potencia"].valor == 0.92
    assert r["dps_ka"].valor == 10
    assert r["ip"].valor == "IP66" and r["ik"].valor == "IK08"
    assert r["lente"].valor == "policarbonato"


def test_rele_simples():
    r = _por_atributo("Relé Fotoelétrico Térmico 220 V")
    assert r["tensao_v"].valor == 220.0 and r["tensao_v"].operador == Operador.IGUAL
    assert inferir_categoria("Relé Fotoelétrico Térmico 220 V") == "rele_fotoeletrico"


def test_categorias():
    assert inferir_categoria(GOIANIRA_100W) == "luminaria_publica_led"
    assert inferir_categoria("POSTE DE AÇO REDONDO GALVANIZADO 7 M.") == "poste"
    assert inferir_categoria("Cabo flexível 2,5 mm² 750V") == "cabo"
    assert inferir_categoria("Bateria estacionária 12V") == "bateria"
    assert inferir_categoria("Veículo SUV zero km") == "outro"
