"""Nó de extração de requisitos (Agente Analista Técnico — parte de interpretação).

Caminho duplo: regras determinísticas sempre rodam; o LLM, quando disponível,
complementa com atributos que as regras não capturaram. Divergências entre os
dois viram pendência de revisão humana, nunca uma escolha silenciosa.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from obranexo.agents.contexto import Contexto
from obranexo.agents.prompts import SYSTEM_EXTRATOR
from obranexo.catalog.atributos import ATRIBUTOS
from obranexo.models import Conflito, ItemDemanda, Operador, Requisito, TipoAtributo
from obranexo.rules.extrair import extrair_requisitos, inferir_categoria


class RequisitoLLM(BaseModel):
    atributo: str = Field(description="Chave de um atributo canônico")
    operador: Literal["=", ">=", "<=", "entre", "contem", "verdadeiro"]
    valor_numero: float | None = None
    valor_faixa: list[float] | None = None
    valor_texto: str | None = None
    valor_booleano: bool | None = None
    unidade: str | None = None
    obrigatorio: bool = True
    trecho_literal: str


class ExtracaoItem(BaseModel):
    categoria: str
    requisitos: list[RequisitoLLM]
    observacoes: list[str] = Field(default_factory=list)


def _valor_llm(r: RequisitoLLM):
    meta = ATRIBUTOS.get(r.atributo, {})
    if meta.get("tipo") == TipoAtributo.ENUM:
        # IP/IK chegam como 66, "66", "IP 66" ou "IP66": guardamos sempre na forma canônica "IP66"
        bruto = r.valor_texto if r.valor_texto is not None else r.valor_numero
        m = re.search(r"(\d{1,2})", str(bruto if bruto is not None else ""))
        if not m:
            return None
        prefixo = "IP" if r.atributo == "ip" else "IK"
        return f"{prefixo}{int(m.group(1)):02d}"
    if r.valor_faixa is not None and len(r.valor_faixa) == 2:
        return [float(r.valor_faixa[0]), float(r.valor_faixa[1])]
    if r.valor_numero is not None:
        return float(r.valor_numero)
    if r.valor_booleano is not None:
        return bool(r.valor_booleano)
    return r.valor_texto


def _mesmo_valor(a, b) -> bool:
    if isinstance(a, list | tuple) and isinstance(b, list | tuple):
        return len(a) == len(b) and all(_mesmo_valor(x, y) for x, y in zip(a, b, strict=False))
    try:
        return abs(float(a) - float(b)) <= 1e-6
    except (TypeError, ValueError):
        return str(a).strip().lower() == str(b).strip().lower()


def extrair_item(ctx: Contexto, item: ItemDemanda, doc_item_id: str) -> list[Requisito]:
    """Extrai os requisitos de um item. `doc_item_id` é o documento virtual com a descrição do item."""
    item.categoria_inferida = item.categoria_inferida or inferir_categoria(item.descricao)
    requisitos: list[Requisito] = []

    # 1) Regras determinísticas (sempre)
    for bruto in extrair_requisitos(item.descricao):
        ev = ctx.nova_evidencia(doc_item_id, 1, bruto.texto_origem)
        requisitos.append(
            Requisito(
                id=ctx.novo_id("req"),
                item_id=item.id,
                atributo=bruto.atributo,
                operador=bruto.operador,
                valor=bruto.valor,
                unidade=bruto.unidade,
                obrigatorio=bruto.obrigatorio,
                texto_origem=bruto.texto_origem,
                evidencia_id=ev.id,
                fonte_extracao="regras",
            )
        )
    ctx.evento("extrair_itens", f"Item {item.numero_item}: {len(requisitos)} requisito(s) por regras", item=item.id)

    # 2) LLM (complementar)
    if not ctx.usar_llm:
        return requisitos
    try:
        prompt = f"<item numero=\"{item.numero_item}\">\n{item.descricao}\n</item>\nExtraia os requisitos técnicos deste item."
        extracao = ctx.llm.extrair(ctx.cfg.model_extracao, SYSTEM_EXTRATOR, prompt, ExtracaoItem)
    except Exception as exc:  # LLM é complementar: falha não derruba a análise
        ctx.evento("extrair_itens", f"Item {item.numero_item}: extrator LLM indisponível ({exc})", item=item.id)
        return requisitos

    if extracao.categoria and item.categoria_inferida == "outro":
        item.categoria_inferida = extracao.categoria
    por_atributo = {r.atributo: r for r in requisitos}
    novos = 0
    for r in extracao.requisitos:
        if r.atributo not in ATRIBUTOS:
            continue
        valor = _valor_llm(r)
        if valor is None:
            continue
        existente = por_atributo.get(r.atributo)
        if existente is not None:
            if not _mesmo_valor(existente.valor, valor) and ATRIBUTOS[r.atributo]["tipo"] != TipoAtributo.TEXTO:
                ctx.analise.conflitos.append(
                    Conflito(
                        atributo=r.atributo,
                        item_id=item.id,
                        valores=[
                            {"fonte": "regras", "valor": existente.valor, "trecho": existente.texto_origem},
                            {"fonte": "llm", "valor": valor, "trecho": r.trecho_literal},
                        ],
                        descricao=f"Extração por regras e por LLM divergem para '{r.atributo}' no item {item.numero_item}.",
                    )
                )
            continue
        ev = ctx.nova_evidencia(doc_item_id, 1, r.trecho_literal)
        # Atributos textuais (fixação, lente, material…) são comparados por semelhança de texto:
        # entram como desejáveis, como já acontece na extração por regras, para não bloquear um item
        # por uma descrição livre que o catálogo não detalha.
        textual = ATRIBUTOS[r.atributo]["tipo"] == TipoAtributo.TEXTO
        requisitos.append(
            Requisito(
                id=ctx.novo_id("req"),
                item_id=item.id,
                atributo=r.atributo,
                operador=Operador(r.operador),
                valor=valor,
                unidade=r.unidade or ATRIBUTOS[r.atributo].get("unidade"),
                obrigatorio=r.obrigatorio and not textual,
                texto_origem=r.trecho_literal,
                evidencia_id=ev.id,
                fonte_extracao="llm",
            )
        )
        novos += 1
    ctx.evento("extrair_itens", f"Item {item.numero_item}: LLM acrescentou {novos} requisito(s)", item=item.id, modelo=ctx.cfg.model_extracao)
    return requisitos
