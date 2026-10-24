"""Especificador: lê no Termo de Referência a especificação dos itens que o PNCP publica só com o nome.

Muitas compras (ex.: material de consumo) publicam itens como "Cabo elétrico flexível" e deixam a seção,
a tensão e a classe para uma tabela do TR. Em vez de investigar item a item (caro e limitado por passos),
o Especificador localiza as páginas do TR que tratam desses itens e lê todas de uma vez com o LLM. Cada
atributo precisa vir com trecho literal, que é conferido no documento antes de virar requisito.
"""

from __future__ import annotations

import re
from collections import Counter

from pydantic import BaseModel, Field

from obranexo.agents.contexto import Contexto
from obranexo.agents.extrator import RequisitoLLM, _valor_bruto_llm
from obranexo.agents.prompts import SYSTEM_ESPECIFICADOR, VERSAO
from obranexo.catalog.atributos import ATRIBUTOS, ATRIBUTOS_INVESTIGAVEIS, natureza
from obranexo.documents.extract import normalizar_busca
from obranexo.evidence.verify import verificar_evidencia
from obranexo.models import ItemDemanda, Operador, Requisito
from obranexo.observability.trilha import escopo
from obranexo.rules.validar import normalizar_valor

MAX_PAGINAS = 14
MAX_CHARS_POR_CHAMADA = 22_000


class ItemEspecificado(BaseModel):
    numero_item: int
    documento_id: str
    pagina: int
    requisitos: list[RequisitoLLM] = Field(default_factory=list)


class EspecificacoesTR(BaseModel):
    itens: list[ItemEspecificado]


def _paginas_relevantes(ctx: Contexto, itens: list[ItemDemanda]) -> list[tuple[str, int]]:
    """Páginas dos anexos que mais falam dos itens (busca pela descrição de cada um)."""
    pontos: Counter = Counter()
    for item in itens:
        for r in ctx.indice.buscar(item.descricao[:160], top_k=4):
            if not r.trecho.documento_id.startswith("pncp-item"):
                pontos[(r.trecho.documento_id, r.trecho.pagina)] += r.score
    return [k for k, _ in pontos.most_common(MAX_PAGINAS)]


def _blocos(ctx: Contexto, paginas: list[tuple[str, int]]) -> list[list[tuple[str, int, str]]]:
    # Proporcional ao lote do provedor (no Groq gratuito, pedidos grandes estouram o limite de tokens por minuto)
    limite = min(MAX_CHARS_POR_CHAMADA, max(6000, int(ctx.cfg.lote_max_chars * 2.4)))
    blocos, atual, tamanho = [], [], 0
    for doc_id, pagina in sorted(paginas):
        texto = ctx.indice.ler_pagina(doc_id, pagina) or ""
        if atual and tamanho + len(texto) > limite:
            blocos.append(atual)
            atual, tamanho = [], 0
        atual.append((doc_id, pagina, texto))
        tamanho += len(texto)
    if atual:
        blocos.append(atual)
    return blocos


_CABECALHO_ITEM = re.compile(r"(?:^|\s)(?:item\s*)?(\d{1,4})\s*[-–]\s+[a-z]")


def item_do_trecho(texto_pagina: str, trecho: str) -> int | None:
    """Em páginas que listam itens numerados ("19 - Cabo elétrico…", "20 - Cabo…"), devolve o número do item
    a que o trecho pertence (o último cabeçalho antes dele). None quando a página não é uma listagem."""
    pagina = normalizar_busca(texto_pagina)
    alvo = normalizar_busca(trecho)[:60]
    if not alvo:
        return None
    pos = pagina.find(alvo)
    if pos < 0:
        return None
    cabecalhos = list(_CABECALHO_ITEM.finditer(pagina))
    if len(cabecalhos) < 2:
        return None
    anteriores = [m for m in cabecalhos if m.start() <= pos]
    return int(anteriores[-1].group(1)) if anteriores else None


def especificar_pelo_tr(ctx: Contexto, itens: list[ItemDemanda]) -> list[Requisito]:
    if not ctx.usar_llm or not itens:
        return []
    paginas = _paginas_relevantes(ctx, itens)
    if not paginas:
        return []
    por_numero = {i.numero_item: i for i in itens}
    lista_itens = "\n".join(f'- item {i.numero_item}: "{i.descricao[:160]}"' for i in itens)
    requisitos: list[Requisito] = []
    rejeitados = 0
    blocos = _blocos(ctx, paginas)
    for bloco in blocos:
        docs = "\n\n".join(f'<documento id="{d}" pagina="{p}">\n{t}\n</documento>' for d, p, t in bloco)
        prompt = (f"ITENS SEM ESPECIFICAÇÃO NO PNCP:\n{lista_itens}\n\nPÁGINAS DOS ANEXOS:\n{docs}\n\n"
                  "Para cada item da lista cuja especificação aparece nestas páginas, extraia os requisitos técnicos.")
        try:
            with escopo(agente="especificador", versao_prompt=VERSAO):
                resp = ctx.llm.extrair(ctx.cfg.model_extracao, SYSTEM_ESPECIFICADOR, prompt, EspecificacoesTR, max_tokens=24000)
        except Exception as exc:
            ctx.evento("especificador", f"Leitura do TR indisponível ({exc})")
            continue
        for it in resp.itens:
            item = por_numero.get(it.numero_item)
            if item is None or it.documento_id not in ctx.indice.paginas:
                continue
            for r in it.requisitos:
                if r.atributo in ATRIBUTOS_INVESTIGAVEIS or natureza(r.atributo) != "produto":
                    continue  # cláusulas gerais ficam com o Investigador
                valor, _ = normalizar_valor(r.atributo, _valor_bruto_llm(r))
                if valor is None:
                    rejeitados += 1
                    continue
                ev = ctx.nova_evidencia(it.documento_id, it.pagina, r.trecho_literal)
                verificar_evidencia(ev, ctx.indice)
                if not ev.verificada:  # trecho que não está no documento não vira requisito
                    ctx.analise.evidencias.remove(ev)
                    rejeitados += 1
                    continue
                # Âncora do item: numa listagem numerada, o trecho precisa estar no bloco DESTE item
                dono = item_do_trecho(ctx.indice.ler_pagina(it.documento_id, ev.pagina) or "", r.trecho_literal)
                if dono is not None and dono != item.numero_item:
                    ctx.analise.evidencias.remove(ev)
                    rejeitados += 1
                    continue
                operador = Operador(r.operador) if r.operador in Operador._value2member_map_ else ATRIBUTOS[r.atributo]["operador_padrao"]
                if isinstance(valor, list):
                    operador = Operador.ENTRE
                requisitos.append(Requisito(
                    id=ctx.novo_id("req"), item_id=item.id, atributo=r.atributo, operador=operador, valor=valor,
                    unidade=ATRIBUTOS[r.atributo].get("unidade"),
                    # Especificação do TR com citação conferida: exigência de verdade, exceto atributos de texto livre
                    obrigatorio=r.obrigatorio and ATRIBUTOS[r.atributo]["tipo"] != "texto",
                    texto_origem=r.trecho_literal, evidencia_id=ev.id, fonte_extracao="documento",
                ))
    especificados = {r.item_id for r in requisitos}
    ctx.evento(
        "especificador",
        f"Especificador (TR): {len(especificados)}/{len(itens)} item(ns) especificado(s) a partir de {len(paginas)} página(s) "
        f"em {len(blocos)} chamada(s); {len(requisitos)} requisito(s) com citação conferida" + (f", {rejeitados} rejeitado(s)" if rejeitados else ""),
        modelo=ctx.cfg.model_extracao,
    )
    return requisitos
