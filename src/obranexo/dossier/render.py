"""Renderização do dossiê comercial em Markdown (seção 11 do roadmap)."""

from __future__ import annotations

from obranexo import __version__
from obranexo.catalog.atributos import rotulo
from obranexo.models import Analise, Empresa, ResultadoItem, ResultadoRequisito

_ICONE = {
    ResultadoItem.COMPATIVEL: "✅",
    ResultadoItem.PARCIAL: "🟡",
    ResultadoItem.INDETERMINADO: "❔",
    ResultadoItem.INCOMPATIVEL: "❌",
}
_ICONE_REQ = {
    ResultadoRequisito.ATENDE: "✅",
    ResultadoRequisito.NAO_ATENDE: "❌",
    ResultadoRequisito.INDETERMINADO: "❔",
}


def _moeda(v: float | None) -> str:
    if v is None:
        return "—"
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_valor(v) -> str:
    if isinstance(v, list | tuple) and len(v) == 2:
        return f"{_fmt_valor(v[0])} a {_fmt_valor(v[1])}"
    if isinstance(v, bool):
        return "sim" if v else "não"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).replace("|", "/").replace("\n", " ") if v is not None else "—"


def _ref_evidencia(analise: Analise, evidencia_id: str | None) -> str:
    ev = analise.evidencia(evidencia_id)
    if not ev:
        return "sem evidência"
    doc = next((d for d in analise.documentos if d.id == ev.documento_id), None)
    nome = doc.nome if doc else ev.documento_id
    pag = f", p.{ev.pagina}" if ev.pagina else ""
    marca = "✔" if ev.verificada else "⚠ não verificada"
    return f"[{nome}{pag}] {marca}"


def renderizar(analise: Analise, empresa: Empresa, resumo: str, proximos_passos: list[str], riscos: list[str]) -> str:
    ct = analise.contratacao
    q = analise.qualificacao
    produtos = {p.id: p for p in empresa.produtos}
    reqs = {r.id: r for r in analise.requisitos}
    L: list[str] = []
    L.append(f"# Dossiê comercial — {ct.orgao_nome}")
    L.append("")
    L.append(f"**Contratação:** {ct.id}  ")
    L.append(f"**Objeto:** {ct.objeto}  ")
    L.append(f"**Modalidade:** {ct.modalidade or '—'} · **Nº:** {ct.numero_compra or '—'}/{ct.ano} · **SRP:** {'sim' if ct.srp else 'não'}  ")
    L.append(f"**Local:** {ct.municipio or '—'}/{ct.uf or '—'} · **Unidade:** {ct.unidade_nome or '—'}  ")
    L.append(f"**Valor estimado:** {_moeda(ct.valor_estimado)} · **Homologado:** {_moeda(ct.valor_homologado)}  ")
    pub = ct.data_publicacao.strftime("%d/%m/%Y") if ct.data_publicacao else "—"
    enc = ct.data_encerramento_proposta.strftime("%d/%m/%Y %H:%M") if ct.data_encerramento_proposta else "—"
    L.append(f"**Publicação:** {pub} · **Encerramento de propostas:** {enc} · **Situação:** {ct.situacao or '—'}  ")
    L.append(f"**Fonte oficial:** {ct.link_oficial or '—'}  ")
    if ct.link_sistema_origem:
        L.append(f"**Sistema de origem:** {ct.link_sistema_origem}  ")
    L.append("")

    if q:
        L.append("## 1. Classificação da oportunidade")
        L.append(f"- **Tipo:** {q.tipo_oportunidade.value}")
        L.append(f"- **Comprador provável:** {q.comprador_provavel}")
        L.append(f"- **Por quê:** {q.justificativa_tipo}")
        L.append(f"- **Prazo:** {q.prazo_status} — {q.prazo_observacao}")
        L.append("")

    L.append("## 2. Resumo executivo")
    L.append(resumo)
    L.append("")

    L.append("## 3. Itens e correspondência com o catálogo")
    L.append("")
    L.append("| Item | Descrição (resumo) | Qtd | Valor unit. | Melhor produto | Resultado | Confiança |")
    L.append("|---|---|---|---|---|---|---|")
    ordem = {ResultadoItem.COMPATIVEL: 3, ResultadoItem.PARCIAL: 2, ResultadoItem.INDETERMINADO: 1, ResultadoItem.INCOMPATIVEL: 0}
    for item in analise.itens:
        cs = sorted((c for c in analise.correspondencias if c.item_id == item.id), key=lambda c: (ordem[c.resultado], c.score), reverse=True)
        desc = item.descricao[:70].replace("|", "/") + ("…" if len(item.descricao) > 70 else "")
        if not cs:
            L.append(f"| {item.numero_item} | {desc} | {_fmt_valor(item.quantidade)} | {_moeda(item.valor_unit_estimado)} | — | fora do portfólio ({item.categoria_inferida}) | — |")
            continue
        c = cs[0]
        p = produtos.get(c.produto_id)
        L.append(
            f"| {item.numero_item} | {desc} | {_fmt_valor(item.quantidade)} | {_moeda(item.valor_unit_estimado)} | "
            f"{p.sku + ' — ' + p.nome if p else c.produto_id} | {_ICONE[c.resultado]} {c.resultado.value} | {c.confianca.value} |"
        )
    L.append("")

    L.append("## 4. Requisitos por item (com evidências)")
    for item in analise.itens:
        cs = sorted((c for c in analise.correspondencias if c.item_id == item.id), key=lambda c: (ordem[c.resultado], c.score), reverse=True)
        if not cs:
            continue
        L.append(f"### Item {item.numero_item} — {item.descricao[:90]}{'…' if len(item.descricao) > 90 else ''}")
        for c in cs[:2]:
            p = produtos.get(c.produto_id)
            L.append(f"**Produto {p.sku if p else c.produto_id} — {p.nome if p else ''}: {_ICONE[c.resultado]} {c.resultado.value} (score {c.score:.2f}, confiança {c.confianca.value})**")
            L.append("")
            L.append("| Requisito | Exigido | Produto | Resultado | Evidência |")
            L.append("|---|---|---|---|---|")
            for d in c.detalhes:
                r = reqs.get(d.requisito_id)
                obrig = "" if (r and r.obrigatorio) else " (desejável)"
                L.append(
                    f"| {rotulo(d.atributo)}{obrig} | {r.operador.value + ' ' if r and r.operador.value not in ('verdadeiro', 'contem') else ''}{_fmt_valor(d.valor_exigido)} "
                    f"| {_fmt_valor(d.valor_produto)} | {_ICONE_REQ[d.resultado]} {d.resultado.value} | {_ref_evidencia(analise, r.evidencia_id if r else None)} |"
                )
            L.append("")

    if analise.insumos_indiretos:
        L.append("## 4b. Insumos do portfólio mencionados nos projetos/orçamentos (oportunidade indireta)")
        L.append("")
        L.append("| Categoria | Documento | Pág. | Trecho |")
        L.append("|---|---|---|---|")
        docs_por_id = {d.id: d for d in analise.documentos}
        for i in analise.insumos_indiretos:
            doc = docs_por_id.get(i["documento_id"])
            trecho = i["trecho"].replace("|", "/").replace("\n", " ")[:200]
            L.append(f"| {i['categoria']} | {doc.nome if doc else i['documento_id']} | {i['pagina']} | {trecho}… |")
        L.append("")
        L.append("*Menções não são pedidos de compra: indicam onde o fornecedor pode procurar quantidades e especificações para abordar a construtora.*")
        L.append("")
    L.append("## 5. Evidências citadas")
    for ev in analise.evidencias:
        doc = next((d for d in analise.documentos if d.id == ev.documento_id), None)
        nome = doc.nome if doc else ev.documento_id
        L.append(f"- **{ev.id}** — {nome}{f', p.{ev.pagina}' if ev.pagina else ''} — {'verificada' if ev.verificada else '⚠ NÃO verificada'}: “{ev.trecho_literal[:220]}{'…' if len(ev.trecho_literal) > 220 else ''}”")
    L.append("")

    L.append("## 6. Lacunas e incertezas")
    L.extend(f"- {x}" for x in analise.lacunas) if analise.lacunas else L.append("- Nenhuma lacuna registrada.")
    L.append("")
    L.append("## 7. Conflitos entre fontes")
    L.extend(f"- {c.descricao}" for c in analise.conflitos) if analise.conflitos else L.append("- Nenhum conflito detectado.")
    L.append("")
    L.append("## 8. Riscos")
    L.extend(f"- {r}" for r in riscos) if riscos else L.append("- Nenhum risco adicional identificado.")
    L.append("")
    if q:
        L.append("## 9. Prioridade")
        L.append(f"**{q.prioridade:.0f}/100** — {q.justificativa_prioridade}")
        L.append("")
    L.append("## 10. Próximos passos recomendados")
    L.extend(f"{i}. {p}" for i, p in enumerate(proximos_passos, start=1))
    L.append("")
    if analise.revisao_humana:
        L.append("## 11. Pendências de revisão humana")
        for x in analise.revisao_humana:
            L.append(f"- {x}" if not x.startswith("Parecer") else "\n" + x + "\n")
        L.append("")
    if analise.passos_investigacao:
        L.append("## 12. Trilha do Agente Investigador")
        for p in analise.passos_investigacao:
            if p.get("tipo") == "ferramenta":
                L.append(f"- Passo {p.get('passo')}: `{p.get('ferramenta')}` {p.get('entrada')} → {str(p.get('saida'))[:160]}")
            else:
                L.append(f"- Passo {p.get('passo')}: {str(p.get('texto'))[:300]}")
        L.append("")
    u = analise.uso_llm
    dur = analise.duracao_s()
    L.append("---")
    L.append(
        f"*ObraNexo v{__version__} · modo {analise.modo} · prompts {analise.versao_prompts} · "
        f"{u.chamadas} chamada(s) LLM ({u.chamadas_cache} do cache) · {u.tokens_entrada + u.tokens_saida + u.tokens_raciocinio} tokens "
        f"({u.tokens_raciocinio} de raciocínio) · custo estimado US$ {u.custo_usd:.4f} · espera pelos modelos {u.latencia_ms / 1000:.0f}s · "
        f"duração {dur:.0f}s · gerado em {analise.iniciada_em:%d/%m/%Y %H:%M}.*"
        if dur is not None
        else f"*ObraNexo v{__version__} · modo {analise.modo}.*"
    )
    L.append("")
    L.append("*Este dossiê é apoio à decisão. A decisão comercial, a conferência final dos documentos e qualquer ato formal perante o órgão são responsabilidade humana.*")
    return "\n".join(L)
