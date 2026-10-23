"""Motor de regras de compatibilidade técnica: compara requisitos com produtos.

Aqui NÃO há LLM. Cada requisito vira ATENDE / NAO_ATENDE / INDETERMINADO com
justificativa, e os resultados são agregados por item.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from rapidfuzz import fuzz

from obranexo.catalog.atributos import ATRIBUTOS, natureza, rotulo
from obranexo.models import (
    Atributo,
    DetalheRequisito,
    Operador,
    Produto,
    Requisito,
    ResultadoItem,
    ResultadoRequisito,
    TipoAtributo,
)


def _norm(texto: Any) -> str:
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t.lower()).strip()


def _fmt(valor: Any, unidade: str | None = None) -> str:
    if isinstance(valor, list | tuple) and len(valor) == 2:
        return f"{_fmt(valor[0])} a {_fmt(valor[1])}{(' ' + unidade) if unidade else ''}"
    if isinstance(valor, bool):
        return "sim" if valor else "não"
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    if isinstance(valor, int | float):
        return f"{valor:,}".replace(",", ".") + (f" {unidade}" if unidade else "")
    return str(valor)


def _enum_num(valor: Any) -> int | None:
    m = re.search(r"(\d{2})", str(valor))
    return int(m.group(1)) if m else None


def _como_numero(atr: Atributo) -> float | None:
    if atr.valor is None:
        return None
    if isinstance(atr.valor, list | tuple):
        return None
    if isinstance(atr.valor, bool):
        return None
    try:
        return float(atr.valor)
    except (TypeError, ValueError):
        return _enum_num(atr.valor)


def _como_faixa(atr: Atributo) -> tuple[float, float] | None:
    if isinstance(atr.valor, list | tuple) and len(atr.valor) == 2:
        return float(atr.valor[0]), float(atr.valor[1])
    n = _como_numero(atr)
    return (n, n) if n is not None else None


def comparar_requisito(req: Requisito, produto: Produto) -> DetalheRequisito:
    meta = ATRIBUTOS.get(req.atributo, {})
    tipo = meta.get("tipo", TipoAtributo.TEXTO)
    nome = rotulo(req.atributo)
    exigido = _fmt(req.valor, req.unidade)

    def detalhe(resultado: ResultadoRequisito, justificativa: str, valor_produto: Any = None) -> DetalheRequisito:
        return DetalheRequisito(
            requisito_id=req.id,
            atributo=req.atributo,
            resultado=resultado,
            justificativa=justificativa,
            valor_exigido=req.valor,
            valor_produto=valor_produto,
        )

    # Exigências documentais: comparadas com certificações/documentos declarados pelo fornecedor
    if natureza(req.atributo) == "documental":
        docs = " | ".join(produto.certificacoes + produto.normas)
        chaves = {
            "doc_termo_garantia": ["termo de garantia", "garantia"],
            "doc_registro_inmetro": ["inmetro"],
            "doc_ensaios": ["ensaio", "laudo"],
            "doc_curva_ies": ["ies", "fotometric"],
            "doc_amostra": ["amostra"],
        }.get(req.atributo, [])
        if not docs:
            return detalhe(ResultadoRequisito.INDETERMINADO, f"{nome}: o catálogo não informa os documentos disponíveis para o produto.")
        encontrados = [d for d in produto.certificacoes + produto.normas if any(k in _norm(d) for k in chaves)]
        if encontrados:
            return detalhe(ResultadoRequisito.ATENDE, f"{nome}: fornecedor declara possuir ({'; '.join(encontrados)}).", "; ".join(encontrados))
        if req.atributo == "doc_amostra":
            return detalhe(ResultadoRequisito.INDETERMINADO, f"{nome}: exigência operacional (envio de amostra) — não depende do catálogo, depende de decisão comercial.", "—")
        return detalhe(ResultadoRequisito.NAO_ATENDE, f"{nome}: exigido no edital, mas não consta entre os documentos declarados pelo fornecedor.", "não declarado")

    atr = produto.atributos.get(req.atributo)
    if atr is None and req.atributo == "prazo_entrega_dias" and produto.prazo_entrega_dias is not None:
        atr = Atributo(valor=float(produto.prazo_entrega_dias), unidade="dias", tipo=TipoAtributo.NUMERO)
    if atr is None or atr.valor is None:
        return detalhe(ResultadoRequisito.INDETERMINADO, f"{nome}: o catálogo não informa este atributo para o produto (exigido: {exigido}).")

    # --- Booleanos ---------------------------------------------------
    if tipo == TipoAtributo.BOOLEANO or req.operador == Operador.VERDADEIRO:
        ok = bool(atr.valor)
        return detalhe(
            ResultadoRequisito.ATENDE if ok else ResultadoRequisito.NAO_ATENDE,
            f"{nome}: exigido; produto {'possui' if ok else 'NÃO possui'}.",
            atr.valor,
        )

    # --- Enumerações ordinais (IP, IK) -------------------------------
    if tipo == TipoAtributo.ENUM:
        ex, pr = _enum_num(req.valor), _enum_num(atr.valor)
        if ex is None or pr is None:
            return detalhe(ResultadoRequisito.INDETERMINADO, f"{nome}: valores não comparáveis (exigido {req.valor}, produto {atr.valor}).", atr.valor)
        ok = pr >= ex if req.operador != Operador.IGUAL else pr == ex
        return detalhe(
            ResultadoRequisito.ATENDE if ok else ResultadoRequisito.NAO_ATENDE,
            f"{nome}: exigido {req.valor}, produto {atr.valor} ({'atende' if ok else 'inferior ao exigido'}).",
            atr.valor,
        )

    # --- Texto (contém) ----------------------------------------------
    if tipo == TipoAtributo.TEXTO or req.operador == Operador.CONTEM:
        alvo = _norm(req.valor)
        base = _norm(atr.valor)
        if req.atributo == "classe_isolacao":
            romanos = {"i": "1", "ii": "2", "iii": "3"}
            alvo, base = romanos.get(alvo, alvo), romanos.get(base, base)
        if req.atributo == "tipo_cabo":
            # Valores curtos ("pp", "nu"): similaridade aproximada daria falso acerto; exige a palavra exata
            ok = re.search(rf"\b{re.escape(alvo)}\b", base) is not None
            return detalhe(
                ResultadoRequisito.ATENDE if ok else ResultadoRequisito.NAO_ATENDE,
                f"{nome}: exigido '{req.valor}', produto '{atr.valor}'.",
                atr.valor,
            )
        if req.atributo == "frequencia_hz":
            # "50/60" exigido: produto precisa cobrir ambas; "60" exigido: basta conter 60
            exigidas = set(re.findall(r"50|60", alvo))
            possui = set(re.findall(r"50|60", base))
            ok = exigidas.issubset(possui)
        else:
            ok = alvo in base or fuzz.partial_ratio(alvo, base) >= 85
            # Textos de medida ("tubo 33 à Ø 60,3mm" x "braço 33 a 60,3 mm"): se todas as medidas exigidas
            # aparecem no produto, o requisito é atendido mesmo com redação diferente
            numeros_exigidos = set(re.findall(r"\d+(?:[.,]\d+)?", alvo))
            if not ok and numeros_exigidos:
                numeros_produto = {n.replace(",", ".") for n in re.findall(r"\d+(?:[.,]\d+)?", base)}
                ok = {n.replace(",", ".") for n in numeros_exigidos} <= numeros_produto
        return detalhe(
            ResultadoRequisito.ATENDE if ok else ResultadoRequisito.NAO_ATENDE,
            f"{nome}: exigido '{req.valor}', produto '{atr.valor}'.",
            atr.valor,
        )

    # --- Faixas (tensão, temperatura) --------------------------------
    if tipo == TipoAtributo.FAIXA:
        faixa_prod = _como_faixa(atr)
        if faixa_prod is None:
            return detalhe(ResultadoRequisito.INDETERMINADO, f"{nome}: valor do produto não interpretável ({atr.valor}).", atr.valor)
        pmin, pmax = faixa_prod
        if isinstance(req.valor, list | tuple) and len(req.valor) == 2:
            rmin, rmax = float(req.valor[0]), float(req.valor[1])
            if meta.get("cobertura"):
                ok = pmin <= rmin and pmax >= rmax
                txt = "cobre" if ok else "NÃO cobre"
            else:
                ok = rmin <= pmin and pmax <= rmax
                txt = "dentro da faixa" if ok else "fora da faixa"
            return detalhe(
                ResultadoRequisito.ATENDE if ok else ResultadoRequisito.NAO_ATENDE,
                f"{nome}: exigido {exigido}; produto {_fmt([pmin, pmax], atr.unidade)} ({txt}).",
                [pmin, pmax],
            )
        v = float(req.valor)
        ok = pmin <= v <= pmax
        return detalhe(
            ResultadoRequisito.ATENDE if ok else ResultadoRequisito.NAO_ATENDE,
            f"{nome}: exigido {exigido}; produto opera em {_fmt([pmin, pmax], atr.unidade)} ({'compatível' if ok else 'incompatível'}).",
            [pmin, pmax],
        )

    # --- Números -----------------------------------------------------
    vp = _como_numero(atr)
    if vp is None:
        faixa = _como_faixa(atr)
        if faixa is None:
            return detalhe(ResultadoRequisito.INDETERMINADO, f"{nome}: valor do produto não interpretável ({atr.valor}).", atr.valor)
        vp = faixa[1] if req.operador == Operador.MAIOR_IGUAL else faixa[0]
    tolerancia = float(meta.get("tolerancia", 0.0))
    if req.operador == Operador.ENTRE and isinstance(req.valor, list | tuple):
        rmin, rmax = float(req.valor[0]), float(req.valor[1])
        ok = rmin * (1 - tolerancia) <= vp <= rmax * (1 + tolerancia)
    elif req.operador == Operador.MAIOR_IGUAL:
        ve = float(req.valor)
        ok = vp >= ve
    elif req.operador == Operador.MENOR_IGUAL:
        ve = float(req.valor)
        ok = vp <= ve
    else:
        ve = float(req.valor)
        ok = abs(vp - ve) <= abs(ve) * tolerancia
    op_txt = {Operador.MAIOR_IGUAL: "mínimo", Operador.MENOR_IGUAL: "máximo", Operador.ENTRE: "entre"}.get(req.operador, "igual a")
    return detalhe(
        ResultadoRequisito.ATENDE if ok else ResultadoRequisito.NAO_ATENDE,
        f"{nome}: exigido {op_txt} {exigido}; produto {_fmt(vp, atr.unidade)} ({'atende' if ok else 'não atende'}).",
        vp,
    )


def agregar(detalhes: list[DetalheRequisito], requisitos: dict[str, Requisito]) -> tuple[ResultadoItem, float]:
    """Agrega os resultados de um item e calcula o score de ordenação (0 a 1)."""
    if not detalhes:
        return ResultadoItem.INDETERMINADO, 0.0
    obrig_nao = obrig_indet = desej_nao = False
    pontos = peso_total = 0.0
    for d in detalhes:
        obrigatorio = requisitos[d.requisito_id].obrigatorio if d.requisito_id in requisitos else True
        peso = 2.0 if obrigatorio else 1.0
        peso_total += peso
        if d.resultado == ResultadoRequisito.ATENDE:
            pontos += peso
        elif d.resultado == ResultadoRequisito.INDETERMINADO:
            pontos += peso * 0.4
            obrig_indet |= obrigatorio
        else:
            if obrigatorio:
                obrig_nao = True
            else:
                desej_nao = True
    score = round(pontos / peso_total, 4) if peso_total else 0.0
    if obrig_nao:
        return ResultadoItem.INCOMPATIVEL, score
    if obrig_indet:
        return ResultadoItem.INDETERMINADO, score
    if desej_nao:
        return ResultadoItem.PARCIAL, score
    return ResultadoItem.COMPATIVEL, score


def comparar_requisito_seguro(req: Requisito, produto: Produto) -> DetalheRequisito:
    """Um valor que não dá para interpretar vira INDETERMINADO — nunca derruba a análise inteira
    (no teste cego, `cct_k = "branca fria"` vindo do LLM quebrava a comparação de todos os itens)."""
    try:
        return comparar_requisito(req, produto)
    except (TypeError, ValueError, IndexError) as exc:
        return DetalheRequisito(
            requisito_id=req.id,
            atributo=req.atributo,
            resultado=ResultadoRequisito.INDETERMINADO,
            justificativa=f"{rotulo(req.atributo)}: valor não interpretável ({req.valor!r}; {type(exc).__name__}).",
            valor_exigido=req.valor,
        )


def comparar_item(requisitos: list[Requisito], produto: Produto) -> tuple[ResultadoItem, float, list[DetalheRequisito]]:
    detalhes = [comparar_requisito_seguro(r, produto) for r in requisitos]
    resultado, score = agregar(detalhes, {r.id: r for r in requisitos})
    return resultado, score, detalhes
