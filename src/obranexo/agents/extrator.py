"""Nó de extração de requisitos (Agente Analista Técnico — parte de interpretação).

Caminho duplo: regras determinísticas sempre rodam; o LLM, quando disponível,
complementa com atributos que as regras não capturaram. Divergências entre os
dois viram pendência de revisão humana, nunca uma escolha silenciosa.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from obranexo.agents.contexto import Contexto
from obranexo.agents.prompts import SYSTEM_EXTRATOR
from obranexo.catalog.atributos import ATRIBUTOS
from obranexo.models import Conflito, ItemDemanda, Operador, Requisito, TipoAtributo
from obranexo.rules.extrair import eh_acessorio, extrair_requisitos, inferir_categoria
from obranexo.rules.validar import normalizar_valor


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


def _valor_bruto_llm(r: RequisitoLLM):
    """O valor como o modelo mandou, no campo que ele escolheu (a validação vem depois)."""
    if r.valor_faixa is not None and len(r.valor_faixa) == 2:
        return list(r.valor_faixa)
    if r.valor_numero is not None:
        return r.valor_numero
    if r.valor_booleano is not None:
        return r.valor_booleano
    return r.valor_texto


def prompt_item(item: ItemDemanda) -> str:
    return f'<item numero="{item.numero_item}">\n{item.descricao}\n</item>\nExtraia os requisitos técnicos deste item.'


def chamar_extrator(ctx: Contexto, item: ItemDemanda) -> ExtracaoItem:
    """Só a chamada ao modelo (fica no cache em disco) — usada também para pré-carregar itens em paralelo."""
    return ctx.llm.extrair(ctx.cfg.model_extracao, SYSTEM_EXTRATOR, prompt_item(item), ExtracaoItem)


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
        extracao = chamar_extrator(ctx, item)
    except Exception as exc:  # LLM é complementar: falha não derruba a análise
        ctx.evento("extrair_itens", f"Item {item.numero_item}: extrator LLM indisponível ({exc})", item=item.id)
        return requisitos

    # O LLM só sugere categoria quando as regras não reconheceram o item — nunca para um acessório,
    # que as regras tiram do portfólio de propósito ("suporte para luminária" não é luminária).
    if extracao.categoria and item.categoria_inferida == "outro" and not eh_acessorio(item.descricao):
        item.categoria_inferida = extracao.categoria
    por_atributo = {r.atributo: r for r in requisitos}
    novos = 0
    descartados: list[str] = []
    for r in extracao.requisitos:
        valor, motivo = normalizar_valor(r.atributo, _valor_bruto_llm(r))
        if valor is None:
            descartados.append(f"{r.atributo}: {motivo}")
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
        # O que SÓ o LLM encontrou entra como desejável: aparece no dossiê e pode deixar o item PARCIAL,
        # mas sozinho não o torna INCOMPATÍVEL — as regras decidem. (No teste cego, requisitos inventados
        # pelo LLM — tensão de isolação como alimentação, cor como material — derrubavam itens corretos.)
        operador = Operador(r.operador) if r.operador in Operador._value2member_map_ else ATRIBUTOS[r.atributo]["operador_padrao"]
        if isinstance(valor, list) and operador not in (Operador.ENTRE,):
            operador = Operador.ENTRE
        requisitos.append(
            Requisito(
                id=ctx.novo_id("req"),
                item_id=item.id,
                atributo=r.atributo,
                operador=operador,
                valor=valor,
                unidade=ATRIBUTOS[r.atributo].get("unidade"),
                obrigatorio=False,
                texto_origem=r.trecho_literal,
                evidencia_id=ev.id,
                fonte_extracao="llm",
            )
        )
        novos += 1
    msg = f"Item {item.numero_item}: LLM acrescentou {novos} requisito(s)"
    if descartados:
        msg += f"; {len(descartados)} valor(es) descartado(s) na validação ({'; '.join(descartados[:3])})"
    ctx.evento("extrair_itens", msg, item=item.id, modelo=ctx.cfg.model_extracao)
    return requisitos
