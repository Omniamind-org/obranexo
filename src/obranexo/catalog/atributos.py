"""Registro canônico de atributos técnicos do segmento elétrico/iluminação.

Cada atributo define como é comparado pelo motor de regras:
  tipo ............ numero | faixa | enum | texto | booleano
  operador_padrao . operador assumido quando o texto da demanda não diz "mínimo"/"máximo"
  tolerancia ...... tolerância relativa para o operador "=" (ex.: 10% na potência)
  cobertura ....... (faixa) a faixa do produto precisa COBRIR a faixa exigida (tensão, temperatura)
  natureza ........ produto | documental (exigências de documentos, comparadas às certificações)
"""

from __future__ import annotations

from obranexo.models import Operador, TipoAtributo

ATRIBUTOS: dict[str, dict] = {
    "potencia_w": {"rotulo": "Potência", "unidade": "W", "tipo": TipoAtributo.NUMERO, "operador_padrao": Operador.IGUAL, "tolerancia": 0.10},
    "tensao_v": {"rotulo": "Tensão de alimentação", "unidade": "V", "tipo": TipoAtributo.FAIXA, "operador_padrao": Operador.ENTRE, "cobertura": True},
    "frequencia_hz": {"rotulo": "Frequência", "unidade": "Hz", "tipo": TipoAtributo.TEXTO, "operador_padrao": Operador.CONTEM},
    "cct_k": {"rotulo": "Temperatura de cor", "unidade": "K", "tipo": TipoAtributo.NUMERO, "operador_padrao": Operador.IGUAL, "tolerancia": 0.05},
    "fluxo_lm": {"rotulo": "Fluxo luminoso", "unidade": "lm", "tipo": TipoAtributo.NUMERO, "operador_padrao": Operador.MAIOR_IGUAL},
    "eficiencia_lm_w": {"rotulo": "Eficiência luminosa", "unidade": "lm/W", "tipo": TipoAtributo.NUMERO, "operador_padrao": Operador.MAIOR_IGUAL},
    "irc": {"rotulo": "Índice de reprodução de cor (IRC)", "unidade": None, "tipo": TipoAtributo.NUMERO, "operador_padrao": Operador.MAIOR_IGUAL},
    "fator_potencia": {"rotulo": "Fator de potência", "unidade": None, "tipo": TipoAtributo.NUMERO, "operador_padrao": Operador.MAIOR_IGUAL},
    "ip": {"rotulo": "Grau de proteção (IP)", "unidade": None, "tipo": TipoAtributo.ENUM, "operador_padrao": Operador.MAIOR_IGUAL},
    "ik": {"rotulo": "Resistência a impacto (IK)", "unidade": None, "tipo": TipoAtributo.ENUM, "operador_padrao": Operador.MAIOR_IGUAL},
    "vida_util_h": {"rotulo": "Vida útil", "unidade": "h", "tipo": TipoAtributo.NUMERO, "operador_padrao": Operador.MAIOR_IGUAL},
    "garantia_anos": {"rotulo": "Garantia", "unidade": "anos", "tipo": TipoAtributo.NUMERO, "operador_padrao": Operador.MAIOR_IGUAL},
    "inmetro": {"rotulo": "Certificação INMETRO", "unidade": None, "tipo": TipoAtributo.BOOLEANO, "operador_padrao": Operador.VERDADEIRO},
    "dimerizavel": {"rotulo": "Dimerização", "unidade": None, "tipo": TipoAtributo.BOOLEANO, "operador_padrao": Operador.VERDADEIRO},
    "tomada_rele": {"rotulo": "Tomada/base para relé fotoelétrico", "unidade": None, "tipo": TipoAtributo.BOOLEANO, "operador_padrao": Operador.VERDADEIRO},
    "dps_ka": {"rotulo": "Proteção contra surtos (DPS)", "unidade": "kA", "tipo": TipoAtributo.NUMERO, "operador_padrao": Operador.MAIOR_IGUAL},
    "classe_isolacao": {"rotulo": "Classe de isolação", "unidade": None, "tipo": TipoAtributo.TEXTO, "operador_padrao": Operador.CONTEM},
    "temp_operacao_c": {"rotulo": "Temperatura de operação", "unidade": "°C", "tipo": TipoAtributo.FAIXA, "operador_padrao": Operador.ENTRE, "cobertura": True},
    "material_corpo": {"rotulo": "Material do corpo", "unidade": None, "tipo": TipoAtributo.TEXTO, "operador_padrao": Operador.CONTEM},
    "lente": {"rotulo": "Lente/difusor", "unidade": None, "tipo": TipoAtributo.TEXTO, "operador_padrao": Operador.CONTEM},
    "led_tipo": {"rotulo": "Tipo de LED", "unidade": None, "tipo": TipoAtributo.TEXTO, "operador_padrao": Operador.CONTEM},
    "angulo_abertura": {"rotulo": "Ângulo de abertura", "unidade": None, "tipo": TipoAtributo.TEXTO, "operador_padrao": Operador.CONTEM},
    "fixacao": {"rotulo": "Fixação/encaixe", "unidade": None, "tipo": TipoAtributo.TEXTO, "operador_padrao": Operador.CONTEM},
    "corrente_a": {"rotulo": "Corrente nominal", "unidade": "A", "tipo": TipoAtributo.NUMERO, "operador_padrao": Operador.IGUAL, "tolerancia": 0.0},
    "secao_mm2": {"rotulo": "Seção nominal", "unidade": "mm²", "tipo": TipoAtributo.NUMERO, "operador_padrao": Operador.IGUAL, "tolerancia": 0.0},
    # Sem isto, um cabo solar casava com cabo de instalação predial só porque a seção era igual
    "tipo_cabo": {"rotulo": "Tipo/construção do cabo", "unidade": None, "tipo": TipoAtributo.TEXTO, "operador_padrao": Operador.CONTEM},
    "prazo_entrega_dias": {"rotulo": "Prazo de entrega", "unidade": "dias", "tipo": TipoAtributo.NUMERO, "operador_padrao": Operador.MENOR_IGUAL},
    # Exigências documentais: comparadas com as certificações/documentos que o fornecedor declara possuir
    "doc_termo_garantia": {"rotulo": "Termo de garantia do fabricante", "tipo": TipoAtributo.TEXTO, "operador_padrao": Operador.CONTEM, "natureza": "documental"},
    "doc_registro_inmetro": {"rotulo": "Registro INMETRO (documento)", "tipo": TipoAtributo.TEXTO, "operador_padrao": Operador.CONTEM, "natureza": "documental"},
    "doc_ensaios": {"rotulo": "Relatórios de ensaio", "tipo": TipoAtributo.TEXTO, "operador_padrao": Operador.CONTEM, "natureza": "documental"},
    "doc_curva_ies": {"rotulo": "Curva fotométrica (IES)", "tipo": TipoAtributo.TEXTO, "operador_padrao": Operador.CONTEM, "natureza": "documental"},
    "doc_amostra": {"rotulo": "Apresentação de amostra", "tipo": TipoAtributo.TEXTO, "operador_padrao": Operador.CONTEM, "natureza": "documental"},
}

# Atributos que o Agente Investigador tenta localizar no edital quando faltam na descrição do item
ATRIBUTOS_INVESTIGAVEIS: dict[str, list[str]] = {
    "garantia_anos": ["garantia", "prazo de garantia", "garantia mínima"],
    "prazo_entrega_dias": ["prazo de entrega", "entrega dos produtos", "prazo para entrega", "dias para entrega"],
    "doc_amostra": ["amostra", "apresentação de amostra", "amostras"],
    "inmetro": ["inmetro", "certificação inmetro", "selo inmetro"],
    "doc_ensaios": ["ensaios", "laudo", "relatório de ensaio"],
}


def rotulo(atributo: str) -> str:
    return ATRIBUTOS.get(atributo, {}).get("rotulo", atributo)


def unidade(atributo: str) -> str | None:
    return ATRIBUTOS.get(atributo, {}).get("unidade")


def natureza(atributo: str) -> str:
    return ATRIBUTOS.get(atributo, {}).get("natureza", "produto")
