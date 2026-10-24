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


class ItemExtraido(BaseModel):
    numero_item: int
    categoria: str
    requisitos: list[RequisitoLLM]


class ExtracaoLote(BaseModel):
    itens: list[ItemExtraido]


def prompt_item(item: ItemDemanda) -> str:
    return f'<item numero="{item.numero_item}">\n{item.descricao}\n</item>\nExtraia os requisitos técnicos deste item.'


def chamar_extrator(ctx: Contexto, item: ItemDemanda) -> ExtracaoItem:
    """Extração de um item só (fallback quando o lote falha ou não traz o item)."""
    return ctx.llm.extrair(ctx.cfg.model_extracao, SYSTEM_EXTRATOR, prompt_item(item), ExtracaoItem)


# Limites de um lote: mantêm a saída bem abaixo do teto do modelo e o erro de um lote não custa muito
_LOTE_MAX_ITENS = 10
_LOTE_MAX_CHARS = 9000


def _lotes(itens: list[ItemDemanda], max_itens: int = _LOTE_MAX_ITENS, max_chars: int = _LOTE_MAX_CHARS) -> list[list[ItemDemanda]]:
    lotes: list[list[ItemDemanda]] = []
    atual: list[ItemDemanda] = []
    tamanho = 0
    for item in itens:
        n = len(item.descricao)
        if atual and (len(atual) >= max_itens or tamanho + n > max_chars):
            lotes.append(atual)
            atual, tamanho = [], 0
        atual.append(item)
        tamanho += n
    if atual:
        lotes.append(atual)
    return lotes


def extrair_lotes(ctx: Contexto, itens: list[ItemDemanda]) -> dict[int, ExtracaoItem]:
    """Vários itens por chamada ao LLM (até 10). Num pregão de 32 itens: 4 chamadas em vez de 32 —
    é o que torna viável rodar os agentes no nível gratuito, que limita requisições por minuto."""
    if not ctx.usar_llm or not itens:
        return {}
    from concurrent.futures import ThreadPoolExecutor

    # Tamanho do lote por provedor: o Groq gratuito tem limite baixo de tokens por minuto (413 em pedidos grandes)
    lotes = _lotes(itens, ctx.cfg.lote_max_itens, ctx.cfg.lote_max_chars)

    def chamar(lote: list[ItemDemanda]) -> ExtracaoLote | None:
        prompt = (
            "\n\n".join(f'<item numero="{i.numero_item}">\n{i.descricao}\n</item>' for i in lote)
            + f"\n\nExtraia os requisitos técnicos de CADA um dos {len(lote)} itens acima, um objeto por item, "
            "com o mesmo numero_item. Os requisitos de um item vêm só da descrição DELE."
        )
        try:
            return ctx.llm.extrair(ctx.cfg.model_extracao, SYSTEM_EXTRATOR, prompt, ExtracaoLote, max_tokens=24000)
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=max(1, min(ctx.cfg.llm_paralelo, len(lotes)))) as pool:
        respostas = list(pool.map(chamar, lotes))
    resultado: dict[int, ExtracaoItem] = {}
    validos = {i.numero_item for i in itens}
    for resp in respostas:
        for it in (resp.itens if resp else []):
            if it.numero_item in validos and it.numero_item not in resultado:
                resultado[it.numero_item] = ExtracaoItem(categoria=it.categoria, requisitos=it.requisitos)
    falhas = sum(1 for r in respostas if r is None)
    ctx.evento(
        "extrair_itens",
        f"Analista Técnico (LLM): {len(resultado)}/{len(itens)} itens em {len(lotes)} chamada(s)" + (f"; {falhas} lote(s) falharam" if falhas else ""),
        modelo=ctx.cfg.model_extracao,
    )
    return resultado


def _mesmo_valor(a, b) -> bool:
    if isinstance(a, list | tuple) and isinstance(b, list | tuple):
        return len(a) == len(b) and all(_mesmo_valor(x, y) for x, y in zip(a, b, strict=False))
    try:
        return abs(float(a) - float(b)) <= 1e-6
    except (TypeError, ValueError):
        return str(a).strip().lower() == str(b).strip().lower()


def extrair_item(ctx: Contexto, item: ItemDemanda, doc_item_id: str, extracao: ExtracaoItem | None = None) -> list[Requisito]:
    """Extrai os requisitos de um item. `doc_item_id` é o documento virtual com a descrição do item.
    `extracao` vem do lote; se faltar, faz uma chamada só para este item."""
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
    if extracao is None:
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
