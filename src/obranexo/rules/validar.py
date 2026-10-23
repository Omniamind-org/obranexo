"""Validação de valores vindos do LLM antes de virarem requisitos.

O LLM interpreta; as regras decidem. Todo valor proposto por um modelo passa por aqui:
tipo do atributo, unidade canônica e faixa plausível. O que não passar é descartado
(e registrado), nunca comparado — no teste cego de 23/10/2026 o Gemini devolveu
`cct_k = "branca fria"` (derrubou a análise), `tensao_v = 600–1000` (era tensão de
isolação de cabo) e `material_corpo = "PRETA"` (era a cor).
"""

from __future__ import annotations

import re
from typing import Any

from obranexo.catalog.atributos import ATRIBUTOS, natureza
from obranexo.models import TipoAtributo
from obranexo.rules.extrair import numero_br

# Faixa plausível (inclusiva) para atributos numéricos e de faixa
FAIXAS: dict[str, tuple[float, float]] = {
    "potencia_w": (0.5, 5000),
    "tensao_v": (80, 480),  # alimentação; isolação (600 V, 0,6/1 kV, 750 V) fica de fora
    "cct_k": (1800, 7000),
    "fluxo_lm": (50, 500_000),
    "eficiencia_lm_w": (10, 300),
    "irc": (20, 100),
    "fator_potencia": (0.3, 1.0),
    "vida_util_h": (1000, 300_000),
    "garantia_anos": (0.08, 20),
    "dps_ka": (0.5, 100),
    "temp_operacao_c": (-60, 120),
    "corrente_a": (0.1, 6300),
    "secao_mm2": (0.2, 1000),
    "prazo_entrega_dias": (1, 365),
}

TIPOS_CABO = ("fotovoltaico", "logico", "coaxial", "multiplexado", "aluminio", "nu", "pp")

# Palavras que denunciam que o "material" é na verdade uma cor
_CORES = {"preta", "preto", "branca", "branco", "cinza", "azul", "vermelha", "vermelho", "verde", "amarela", "amarelo", "marrom"}


def _numero(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int | float):
        return float(v)
    if isinstance(v, str):
        m = re.search(r"-?\d+(?:[.,]\d+)*", v)
        if not m:
            return None
        s = m.group()
        n = numero_br(s.lstrip("-"))
        if n is None:
            return None
        return -n if s.startswith("-") else n
    return None


def _na_faixa(atributo: str, x: float) -> bool:
    lo, hi = FAIXAS.get(atributo, (float("-inf"), float("inf")))
    return lo <= x <= hi


def normalizar_valor(atributo: str, valor: Any) -> tuple[Any, str | None]:
    """Devolve (valor_normalizado, None) ou (None, motivo_da_rejeição)."""
    meta = ATRIBUTOS.get(atributo)
    if meta is None:
        return None, f"atributo '{atributo}' não é canônico"
    if valor is None or valor == "":
        return None, "valor vazio"
    tipo = meta["tipo"]

    if natureza(atributo) == "documental":
        # Exigência de documento: o que importa é que existe (o "15" de uma amostra é prazo, não o valor)
        return True, None

    if tipo == TipoAtributo.BOOLEANO:
        if isinstance(valor, bool):
            return valor, None
        t = str(valor).strip().lower()
        if t in {"sim", "s", "true", "verdadeiro", "exigido", "1"}:
            return True, None
        if t in {"nao", "não", "n", "false", "falso", "0"}:
            return False, None
        return None, f"esperado sim/não, veio '{valor}'"

    if tipo == TipoAtributo.ENUM:
        m = re.search(r"(\d{1,2})", str(valor))
        if not m or not 0 <= int(m.group(1)) <= 69:
            return None, f"esperado código IP/IK, veio '{valor}'"
        return f"{'IP' if atributo == 'ip' else 'IK'}{int(m.group(1)):02d}", None

    if tipo == TipoAtributo.FAIXA:
        if isinstance(valor, list | tuple):
            nums = [_numero(v) for v in valor[:2]]
        else:
            # "127-277V": o hífen entre números é separador; só é sinal de menos quando não segue
            # outro número ("-10 a 40 °C", "de -20 a +50")
            partes = re.findall(r"(?:(?<!\d)(?<!\d\s)-)?\d+(?:[.,]\d+)?", str(valor))
            nums = [_numero(p) for p in partes[:2]] if partes else [_numero(valor)]
        nums = [n for n in nums if n is not None]
        if not nums:
            return None, f"faixa não numérica: '{valor}'"
        faixa = [min(nums), max(nums)] if len(nums) == 2 else [nums[0], nums[0]]
        if not all(_na_faixa(atributo, n) for n in faixa):
            return None, f"{faixa} fora da faixa plausível {FAIXAS.get(atributo)}"
        return faixa if faixa[0] != faixa[1] else faixa[0], None

    if tipo == TipoAtributo.NUMERO:
        if isinstance(valor, list | tuple) and len(valor) == 2:
            nums = [_numero(v) for v in valor]
            if None in nums or not all(_na_faixa(atributo, n) for n in nums):
                return None, f"faixa inválida '{valor}'"
            return [min(nums), max(nums)], None
        x = _numero(valor)
        if x is None:
            return None, f"esperado número, veio '{valor}'"
        if atributo == "garantia_anos" and isinstance(valor, str) and re.search(r"mes", valor, re.I):
            x = x / 12
        if not _na_faixa(atributo, x):
            return None, f"{x:g} fora da faixa plausível {FAIXAS.get(atributo)}"
        return x, None

    # Texto
    texto = str(valor).strip()
    if atributo == "tipo_cabo":
        t = texto.lower()
        achado = next((tc for tc in TIPOS_CABO if re.search(rf"\b{tc}\b", t)), None)
        return (achado, None) if achado else (None, f"tipo de cabo fora da lista {TIPOS_CABO}: '{texto[:40]}'")
    if atributo == "material_corpo" and texto.lower() in _CORES:
        return None, f"'{texto}' é cor, não material"
    if len(texto) > 80:
        return None, "texto longo demais para um atributo (provável trecho inteiro)"
    return texto, None
