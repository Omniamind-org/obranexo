"""Agente Verificador: confere citações, detecta conflitos e atribui confiança."""

from __future__ import annotations

from collections import defaultdict

from obranexo.agents.contexto import Contexto
from obranexo.agents.prompts import SYSTEM_VERIFICADOR, VERSAO
from obranexo.catalog.atributos import rotulo
from obranexo.evidence.verify import verificar_evidencia
from obranexo.models import Confianca, Conflito, Correspondencia, ResultadoRequisito
from obranexo.observability.trilha import escopo


def _conflitos_entre_fontes(ctx: Contexto) -> None:
    """Mesmo atributo, mesmo item, valores diferentes vindos de fontes distintas."""
    por_chave: dict[tuple[str, str], list] = defaultdict(list)
    for r in ctx.analise.requisitos:
        por_chave[(r.item_id, r.atributo)].append(r)
    ja = {(c.item_id, c.atributo) for c in ctx.analise.conflitos}
    for (item_id, atributo), reqs in por_chave.items():
        if len(reqs) < 2 or (item_id, atributo) in ja:
            continue
        valores = {str(r.valor) for r in reqs}
        if len(valores) > 1:
            item = ctx.analise.item(item_id)
            ctx.analise.conflitos.append(
                Conflito(
                    atributo=atributo,
                    item_id=item_id,
                    valores=[{"fonte": r.fonte_extracao, "valor": r.valor, "trecho": r.texto_origem, "evidencia_id": r.evidencia_id} for r in reqs],
                    descricao=f"Valores diferentes para '{rotulo(atributo)}' no item {item.numero_item if item else item_id}: {', '.join(sorted(valores))}.",
                )
            )


def _confianca(ctx: Contexto, c: Correspondencia) -> Confianca:
    reqs = {r.id: r for r in ctx.analise.requisitos if r.item_id == c.item_id}
    conflitos_item = {k.atributo for k in ctx.analise.conflitos if k.item_id == c.item_id}
    baixa = media = False
    for d in c.detalhes:
        req = reqs.get(d.requisito_id)
        if req is None:
            continue
        ev = ctx.analise.evidencia(req.evidencia_id)
        if d.atributo in conflitos_item:
            baixa = True
        if ev is None or not ev.verificada:
            if req.obrigatorio and d.resultado != ResultadoRequisito.INDETERMINADO:
                baixa = True
            else:
                media = True
        if d.resultado == ResultadoRequisito.INDETERMINADO:
            media = True
    if baixa:
        return Confianca.BAIXA
    return Confianca.MEDIA if media else Confianca.ALTA


def verificar(ctx: Contexto) -> None:
    analise = ctx.analise
    total = verificadas = 0
    for ev in analise.evidencias:
        verificar_evidencia(ev, ctx.indice)
        total += 1
        verificadas += int(ev.verificada)
    ctx.evento("verificador", f"Evidências verificadas: {verificadas}/{total}")

    _conflitos_entre_fontes(ctx)
    if analise.conflitos:
        ctx.evento("verificador", f"{len(analise.conflitos)} conflito(s) detectado(s)")

    for c in analise.correspondencias:
        c.confianca = _confianca(ctx, c)
        if c.confianca == Confianca.BAIXA:
            item = analise.item(c.item_id)
            analise.revisao_humana.append(
                f"Item {item.numero_item if item else c.item_id} × {c.produto_id}: confiança baixa (evidência não verificada ou conflito)."
            )
    for ev in analise.evidencias:
        if not ev.verificada:
            analise.revisao_humana.append(
                f"Evidência {ev.id} ({ev.documento_id}, p.{ev.pagina}) não foi localizada literalmente no documento (score {ev.score_match})."
            )
    # Remove duplicatas preservando ordem
    analise.revisao_humana = list(dict.fromkeys(analise.revisao_humana))

    if ctx.usar_llm and (analise.conflitos or analise.revisao_humana or analise.lacunas):
        try:
            resumo = {
                "conflitos": [c.descricao for c in analise.conflitos],
                "pendencias": analise.revisao_humana[:12],
                "lacunas": analise.lacunas[:12],
                "correspondencias": [
                    {"item": c.item_id, "produto": c.produto_id, "resultado": c.resultado, "confianca": c.confianca,
                     "indeterminados": [d.justificativa for d in c.detalhes if d.resultado == ResultadoRequisito.INDETERMINADO]}
                    for c in analise.correspondencias[:12]
                ],
            }
            import json

            with escopo(agente="verificador", versao_prompt=VERSAO):
                parecer = ctx.llm.texto(ctx.cfg.model_agente, SYSTEM_VERIFICADOR, "Dados da análise:\n" + json.dumps(resumo, ensure_ascii=False, indent=1, default=str))
            if parecer:
                analise.revisao_humana.insert(0, "Parecer do Agente Verificador:\n" + parecer)
                ctx.evento("verificador", "Parecer do Agente Verificador gerado", modelo=ctx.cfg.model_agente)
        except Exception as exc:
            ctx.evento("verificador", f"Parecer LLM indisponível ({exc})")
