"""Extração DETERMINÍSTICA de requisitos técnicos a partir de descrições de itens.

É a camada de regras do ObraNexo: funciona sem LLM, é testável e serve de
cruzamento para o extrator por linguagem. Cada requisito extraído carrega o
trecho literal de origem, que vira a evidência verificável.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from obranexo.catalog.atributos import ATRIBUTOS
from obranexo.models import Operador


@dataclass
class RequisitoBruto:
    atributo: str
    operador: Operador
    valor: Any
    unidade: str | None
    texto_origem: str
    obrigatorio: bool = True


def _sem_acentos(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def numero_br(texto: str) -> float | None:
    """Converte '8.500', '50,000', '0,98', '14000' e '1.671,18' em float."""
    t = texto.strip().replace(" ", "")
    if not t:
        return None
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", t):  # 1.671,18 / 8.500
        t = t.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(,\d{3})+", t):  # 50,000 (milhar com vírgula)
        t = t.replace(",", "")
    elif re.fullmatch(r"\d+,\d+", t):  # 0,98
        t = t.replace(",", ".")
    elif re.fullmatch(r"\d+\.\d{3}", t):  # 8.500 sem vírgula decimal
        t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None


def _janela(texto: str, inicio: int, fim: int, margem: int = 0) -> str:
    return texto[max(0, inicio - margem) : min(len(texto), fim + margem)].strip()


def _operador_por_contexto(contexto: str, padrao: Operador) -> Operador:
    c = _sem_acentos(contexto).lower()
    if re.search(r"\b(maxim[ao]|ate|no maximo|nao superior|inferior ou igual)\b", c):
        return Operador.MENOR_IGUAL
    if re.search(r"\b(minim[ao]|no minimo|ou maior|ou superior|superior|pelo menos|igual ou maior|>=|≥)\b", c):
        return Operador.MAIOR_IGUAL
    return padrao


def inferir_categoria(descricao: str) -> str:
    d = _sem_acentos(descricao).lower()
    regras = [
        ("luminaria_publica_led", r"luminaria.*(publica|led|via|logradouro|iluminacao publica)|luminaria.*led"),
        ("luminaria_interna", r"luminaria|painel (de )?led|plafon"),
        ("rele_fotoeletrico", r"\brele\b.*foto|fotocel|fotocontrol"),
        ("refletor_led", r"refletor|projetor.*led"),
        ("lampada", r"\blampada"),
        ("poste", r"\bposte\b"),
        ("braco_luminaria", r"\bbraco\b"),
        ("disjuntor", r"disjuntor"),
        ("cabo", r"\bcabo\b|\bfio\b|condutor"),
        ("eletroduto", r"eletroduto|conduite"),
        ("quadro", r"\bquadro\b|painel eletrico|centro de distribuicao"),
        ("dispositivos", r"tomada|interruptor|plugue|adaptador"),
        ("transformador", r"transformador"),
        ("bateria", r"bateria|nobreak|no-break"),
    ]
    for categoria, padrao in regras:
        if re.search(padrao, d):
            return categoria
    return "outro"


def extrair_requisitos(descricao: str) -> list[RequisitoBruto]:
    """Aplica as regras ao texto e devolve os requisitos encontrados (um por atributo)."""
    texto = descricao
    t = _sem_acentos(texto)  # mantém posições (NFKD remove só os combinantes, mas pode alterar índices: usamos t para buscar e cortamos em t)
    tu = t.upper()
    encontrados: dict[str, RequisitoBruto] = {}

    def add(atributo: str, valor: Any, m: re.Match, operador: Operador | None = None, contexto_apos: int = 28, obrigatorio: bool = True):
        if atributo in encontrados:
            return
        meta = ATRIBUTOS[atributo]
        # O qualificador ("máxima", "mínima") vem dentro do próprio match ou logo depois ("70 ou maior");
        # nunca antes, para não herdar o qualificador do atributo anterior na frase.
        contexto = t[m.start() : min(len(t), m.end() + contexto_apos)]
        op = operador or _operador_por_contexto(contexto, meta["operador_padrao"])
        encontrados[atributo] = RequisitoBruto(
            atributo=atributo,
            operador=op,
            valor=valor,
            unidade=meta.get("unidade"),
            texto_origem=_janela(texto, m.start(), m.end()),
            obrigatorio=obrigatorio,
        )

    # --- Potência -------------------------------------------------------
    m = re.search(r"POTENCIA\s*(?:NOMINAL\s*)?(?:MAXIMA|MINIMA)?\s*(?:DE\s*)?ENTRE\s*\(?\s*(\d+(?:[.,]\d+)?)\s*W?\s*(?:A|E|-)\s*(\d+(?:[.,]\d+)?)\s*W", tu)
    if m:
        add("potencia_w", [numero_br(m.group(1)), numero_br(m.group(2))], m, Operador.ENTRE)
    else:
        m = re.search(r"POTENCIA\s*(?:NOMINAL\s*)?(?:MAXIMA|MINIMA)?\s*(?:DE\s*)?(\d+(?:[.,]\d+)?)\s*(?:W|WTS|WATTS?)\b", tu) or re.search(
            r"\b(\d+(?:[.,]\d+)?)\s*(?:W|WTS|WATTS)\b(?!\s*/)", tu
        )
        if m:
            add("potencia_w", numero_br(m.group(1)), m)

    # --- Tensão ---------------------------------------------------------
    m = re.search(r"(\d{2,3})\s*(V)?\s*(?:-|A|À|/|ATE)\s*(\d{2,3})\s*(V(?:CA|AC)?)?\b", tu)
    if m and (m.group(2) or m.group(4)) and 90 <= float(m.group(1)) <= 480 and 90 <= float(m.group(3)) <= 480:
        add("tensao_v", [float(m.group(1)), float(m.group(3))], m, Operador.ENTRE)
    elif re.search(r"\bBIVOLT\b", tu):
        m = re.search(r"\bBIVOLT\b", tu)
        add("tensao_v", [127.0, 220.0], m, Operador.ENTRE)
    else:
        m = re.search(r"\b(\d{2,3})\s*V(?:CA|AC|OLTS)?\b", tu)
        if m and 90 <= float(m.group(1)) <= 480:
            add("tensao_v", float(m.group(1)), m, Operador.IGUAL)

    # --- Frequência -----------------------------------------------------
    m = re.search(r"(50\s*(?:/|OU|E)\s*60|60|50)\s*HZ\b", tu)
    if m:
        add("frequencia_hz", m.group(1).replace(" ", ""), m, Operador.CONTEM, obrigatorio=False)

    # --- Temperatura de cor --------------------------------------------
    m = re.search(r"\b([2-6]\d{3})\s*K\b", tu)
    if m:
        add("cct_k", float(m.group(1)), m, Operador.IGUAL)

    # --- Fluxo luminoso -------------------------------------------------
    m = re.search(r"FLUXO\s*LUMINOSO\s*(?:EFETIVO|NOMINAL|MINIMO)?\s*(?:DE\s*)?([\d.,]+)\s*(?:LM|LUMENS?)\b", tu) or re.search(
        r"\b([\d.,]{4,})\s*(?:LM|LUMENS)\b(?!\s*/)", tu
    )
    if m and numero_br(m.group(1)):
        add("fluxo_lm", numero_br(m.group(1)), m)

    # --- Eficiência -----------------------------------------------------
    m = re.search(r"EFICIENCIA\s*(?:LUMINOSA|ENERGETICA)?\s*(?:MINIMA)?\s*(?:DE\s*)?(\d+(?:[.,]\d+)?)\s*LM\s*/\s*W", tu) or re.search(
        r"\b(\d{2,3})\s*LM\s*/\s*W(?:ATT)?\b", tu
    )
    if m:
        add("eficiencia_lm_w", numero_br(m.group(1)), m)

    # --- IRC ------------------------------------------------------------
    m = re.search(r"\bIRC\s*(?:MINIMO|>=|≥)?\s*(\d{2})\b", tu) or re.search(r"REPRODUCAO\s*DE\s*COR\s*(?:\(IRC\))?\s*(?:MINIMO|>=|≥|DE)?\s*(\d{2})\b", tu)
    if m:
        add("irc", float(m.group(1)), m)

    # --- Fator de potência ---------------------------------------------
    m = re.search(r"FATOR\s*DE\s*POTENCIA\s*(?:MINIMO)?\s*\(?\s*(?:>=|≥|DE)?\s*(0[.,]\d+)", tu)
    if m:
        add("fator_potencia", numero_br(m.group(1)), m)

    # --- IP / IK --------------------------------------------------------
    m = re.search(r"\bIP\s*-?\s*(\d{2})\b", tu)
    if m:
        add("ip", f"IP{m.group(1)}", m)
    m = re.search(r"\bIK\s*-?\s*(\d{2})\b", tu)
    if m:
        add("ik", f"IK{m.group(1)}", m)

    # --- Vida útil ------------------------------------------------------
    m = re.search(r"VIDA\s*UTIL\s*(?:MINIMA|NOMINAL)?\s*(?:DE\s*)?([\d.,]+)\s*(?:HORAS|H)\b", tu)
    if m and numero_br(m.group(1)):
        add("vida_util_h", numero_br(m.group(1)), m)

    # --- Garantia -------------------------------------------------------
    m = re.search(r"(\d+)\s*(ANOS?|MESES)\s*DE\s*GARANTIA", tu) or re.search(r"GARANTIA\s*(?:MINIMA|TOTAL)?\s*(?:DE|DO FABRICANTE DE)?\s*(\d+)\s*(ANOS?|MESES)", tu)
    if m:
        anos = float(m.group(1)) / (12 if m.group(2).startswith("MES") else 1)
        add("garantia_anos", anos, m, Operador.MAIOR_IGUAL)

    # --- Booleanos ------------------------------------------------------
    m = re.search(r"\bINMETRO\b", tu)
    if m:
        add("inmetro", True, m, Operador.VERDADEIRO)
    m = re.search(r"DIMERIZ", tu)
    if m:
        add("dimerizavel", True, m, Operador.VERDADEIRO)
    m = re.search(r"(TOMADA|BASE|SOQUETE)\s*(PARA|P/)?\s*RELE", tu)
    if m:
        add("tomada_rele", True, m, Operador.VERDADEIRO)

    # --- DPS ------------------------------------------------------------
    m = re.search(r"\bDPS\b\s*(?:DE)?\s*(?:NO\s*MINIMO)?\s*(\d+)\s*K?A", tu)
    if m:
        add("dps_ka", float(m.group(1)), m, Operador.MAIOR_IGUAL)

    # --- Classe de isolação --------------------------------------------
    m = re.search(r"CLASSE\s*(?:DE\s*(?:EQUIPAMENTO|ISOLA\w+))?\s*(?:CLASSE)?\s*(I{1,3}|[123])\b", tu)
    if m:
        add("classe_isolacao", m.group(1), m, Operador.CONTEM, obrigatorio=False)

    # --- Temperatura de operação ---------------------------------------
    m = re.search(r"TEMPERATURA\s*DE\s*(?:FUNCIONAMENTO|OPERACAO)\s*(?:DE\s*)?(-?\s*\d+)\s*°?\s*C?\s*A\s*\+?\s*(-?\s*\d+)\s*°?\s*C", tu)
    if m:
        a, b = float(m.group(1).replace(" ", "")), float(m.group(2).replace(" ", ""))
        add("temp_operacao_c", [min(a, b), max(a, b)], m, Operador.ENTRE, obrigatorio=False)

    # --- Textuais -------------------------------------------------------
    m = re.search(r"LENTE\s*(?:EM|DE)\s*([A-Z]+)", tu)
    if m:
        add("lente", m.group(1).lower(), m, Operador.CONTEM, obrigatorio=False)
    m = re.search(r"ALUMINIO", tu)
    if m:
        add("material_corpo", "aluminio", m, Operador.CONTEM, obrigatorio=False)
    m = re.search(r"LED\s*(?:TIPO|DO TIPO)\s*(SMD|COB)", tu)
    if m:
        add("led_tipo", m.group(1), m, Operador.CONTEM, obrigatorio=False)
    m = re.search(r"ANGULO\s*DE\s*ABERTURA\s*(?:DE\s*)?(\d+\s*X\s*\d+|\d+°?)", tu)
    if m:
        add("angulo_abertura", m.group(1).replace(" ", ""), m, Operador.CONTEM, obrigatorio=False)

    # --- Elétrica geral (cabos/disjuntores) ----------------------------
    m = re.search(r"\b(\d+(?:[.,]\d+)?)\s*A\b(?!\s*[+/-]?\s*\d{2,3}\s*C)", tu)
    if m and re.search(r"DISJUNTOR|CORRENTE", tu):
        add("corrente_a", numero_br(m.group(1)), m, Operador.IGUAL)
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*MM\s*(?:2|²)", tu)
    if m:
        add("secao_mm2", numero_br(m.group(1)), m, Operador.IGUAL)

    # --- Exigências documentais ----------------------------------------
    for atributo, padrao in (
        ("doc_termo_garantia", r"TERMO\s*DE\s*GARANTIA"),
        ("doc_registro_inmetro", r"REGISTRO\s*(?:DE|DO)?\s*INMETRO"),
        ("doc_ensaios", r"\bENSAIOS?\b|\bLAUDOS?\b"),
        ("doc_curva_ies", r"CURVA\s*FOTOMETRICA|\bIES\b"),
        ("doc_amostra", r"\bAMOSTRAS?\b"),
    ):
        m = re.search(padrao, tu)
        if m:
            add(atributo, True, m, Operador.CONTEM)

    return list(encontrados.values())
