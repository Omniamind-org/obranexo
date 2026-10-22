"""Orquestrador do fluxo agêntico (seção 7 do roadmap).

v0.1 usa uma máquina de estados explícita em Python puro (plano B do roadmap):
cada nó é uma função que lê e escreve no Contexto. A migração para LangGraph é
direta — os nós já têm fronteiras claras.

  carregar_contexto -> coletar_documentos -> extrair_itens -> filtrar_relevantes
  -> casar_com_catalogo -> investigador (se faltar informação) -> re-casar
  -> verificador -> qualificar -> planejador -> gerar_dossie
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from obranexo.agents.contexto import Contexto, OnEvento
from obranexo.agents.extrator import extrair_item
from obranexo.agents.investigador import investigar
from obranexo.agents.planejador import planejar, qualificar
from obranexo.agents.verificador import verificar
from obranexo.catalog.atributos import ATRIBUTOS_INVESTIGAVEIS
from obranexo.config import Config, config
from obranexo.documents.extract import IndiceDocumentos
from obranexo.dossier.render import renderizar
from obranexo.llm.client import criar_llm_client
from obranexo.models import Analise, Contratacao, Correspondencia, Documento, Dossie, Empresa, ItemDemanda, Requisito
from obranexo.rules.compare import comparar_item
from obranexo.rules.extrair import inferir_categoria
from obranexo.storage import store

MAX_PRODUTOS_POR_ITEM = 3
# Categorias de item para as quais exigências contratuais (garantia, prazo, amostra) são relevantes
_CATEGORIAS_COM_EXIGENCIAS_GLOBAIS = {"luminaria_publica_led", "luminaria_interna", "refletor_led", "lampada", "rele_fotoeletrico"}


def _no_coletar_documentos(ctx: Contexto, documentos: list[Documento]) -> None:
    ctx.evento("coletar_documentos", f"Indexando {len(documentos)} documento(s)")
    for doc in documentos:
        ctx.indice.adicionar(doc)
        ctx.analise.documentos.append(doc)
        ctx.evento(
            "coletar_documentos",
            f"{doc.nome}: {doc.paginas} página(s), {'texto extraído' if doc.extraivel else 'sem texto extraível (zip/imagem)'}",
            documento=doc.id,
        )
    # Cada item do PNCP vira um documento virtual citável
    for item in ctx.analise.itens:
        doc = Documento(
            id=f"pncp-item-{item.numero_item}",
            contratacao_id=ctx.analise.contratacao.id,
            nome=f"PNCP · item {item.numero_item}",
            tipo_doc="Registro de item (PNCP)",
            url_origem=ctx.analise.contratacao.link_oficial,
        )
        ctx.indice.adicionar_texto(doc, item.descricao)
        ctx.analise.documentos.append(doc)


def _no_extrair_itens(ctx: Contexto) -> None:
    for item in ctx.analise.itens:
        item.categoria_inferida = inferir_categoria(item.descricao)
        reqs = extrair_item(ctx, item, f"pncp-item-{item.numero_item}")
        ctx.analise.requisitos.extend(reqs)


def _no_filtrar_relevantes(ctx: Contexto) -> list[ItemDemanda]:
    categorias = ctx.empresa.categorias()
    relevantes = [i for i in ctx.analise.itens if i.categoria_inferida in categorias]
    fora = [i for i in ctx.analise.itens if i.categoria_inferida not in categorias]
    ctx.evento("filtrar_relevantes", f"{len(relevantes)} item(ns) nas categorias do catálogo; {len(fora)} fora do portfólio")
    for i in fora:
        ctx.evento("filtrar_relevantes", f"Item {i.numero_item} ({i.categoria_inferida}) fora do portfólio", item=i.id)
    return relevantes


def _casar(ctx: Contexto, itens: list[ItemDemanda]) -> None:
    ctx.analise.correspondencias = [c for c in ctx.analise.correspondencias if c.item_id not in {i.id for i in itens}]
    for item in itens:
        reqs = [r for r in ctx.analise.requisitos if r.item_id == item.id]
        candidatos = [p for p in ctx.empresa.produtos if p.categoria == item.categoria_inferida]
        resultados = []
        for p in candidatos:
            resultado, score, detalhes = comparar_item(reqs, p)
            resultados.append(Correspondencia(id=ctx.novo_id("corr"), item_id=item.id, produto_id=p.id, resultado=resultado, detalhes=detalhes, score=score))
        ordem = {"COMPATIVEL": 3, "PARCIAL": 2, "INDETERMINADO": 1, "INCOMPATIVEL": 0}
        resultados.sort(key=lambda c: (ordem[c.resultado.value], c.score), reverse=True)
        ctx.analise.correspondencias.extend(resultados[:MAX_PRODUTOS_POR_ITEM])
        melhor = resultados[0].resultado.value if resultados else "sem candidatos"
        ctx.evento("casar_com_catalogo", f"Item {item.numero_item}: {len(candidatos)} candidato(s); melhor = {melhor}", item=item.id)


def _no_investigador(ctx: Contexto, itens: list[ItemDemanda]) -> list[ItemDemanda]:
    """Procura exigências contratuais ausentes nas descrições (garantia, prazo de entrega, amostra...)."""
    alvo = [i for i in itens if i.categoria_inferida in _CATEGORIAS_COM_EXIGENCIAS_GLOBAIS]
    if not alvo:
        return []
    presentes_em_todos = set(ATRIBUTOS_INVESTIGAVEIS)
    for item in alvo:
        presentes_em_todos &= {r.atributo for r in ctx.analise.requisitos if r.item_id == item.id}
    faltantes = [a for a in ATRIBUTOS_INVESTIGAVEIS if a not in presentes_em_todos]
    if not any(d.extraivel for d in ctx.analise.documentos if not d.id.startswith("pncp-item")):
        ctx.evento("investigador", "Nenhum documento com texto extraível; investigação não é possível.")
        ctx.analise.lacunas.append("Os anexos da contratação não têm texto extraível; exigências do edital (garantia, prazo, amostra) não puderam ser verificadas.")
        return []
    achados = investigar(ctx, faltantes)
    # As cláusulas gerais do edital valem como obrigatórias para a categoria principal da contratação
    # (a de maior valor); para as demais categorias entram como desejáveis, pois podem referir-se só ao objeto principal.
    valor_por_categoria: dict[str, float] = {}
    for item in alvo:
        valor_por_categoria[item.categoria_inferida] = valor_por_categoria.get(item.categoria_inferida, 0.0) + (item.quantidade or 0) * (item.valor_unit_estimado or 0)
    categoria_principal = max(valor_por_categoria, key=valor_por_categoria.get) if valor_por_categoria else None
    afetados: list[ItemDemanda] = []
    for item in alvo:
        existentes = {r.atributo for r in ctx.analise.requisitos if r.item_id == item.id}
        for ach in achados:
            if ach.atributo in existentes:
                continue
            obrigatorio = ach.obrigatorio and item.categoria_inferida == categoria_principal
            ctx.analise.requisitos.append(
                Requisito(
                    id=ctx.novo_id("req"), item_id=item.id, atributo=ach.atributo, operador=ach.operador, valor=ach.valor, unidade=ach.unidade,
                    obrigatorio=obrigatorio, texto_origem=ach.texto_origem, evidencia_id=ach.evidencia_id, fonte_extracao="investigador",
                )
            )
            if item not in afetados:
                afetados.append(item)
    ctx.evento("investigador", f"{len(achados)} informação(ões) encontrada(s); {len(afetados)} item(ns) reavaliado(s)")
    return afetados


_TERMOS_INSUMOS = {
    "luminaria_publica_led": ["luminária led", "luminária pública", "iluminação pública"],
    "luminaria_interna": ["luminária", "painel led", "plafon"],
    "refletor_led": ["refletor led", "projetor led"],
    "lampada": ["lâmpada led"],
    "rele_fotoeletrico": ["relé fotoelétrico"],
    "cabo": ["cabo flexível", "cabo de cobre", "condutor"],
    "disjuntor": ["disjuntor"],
    "eletroduto": ["eletroduto"],
    "quadro": ["quadro de distribuição"],
    "dispositivos": ["tomada 2p+t", "interruptor"],
    "braco_luminaria": ["braço para luminária"],
}


def _no_varrer_insumos_indiretos(ctx: Contexto) -> None:
    """Quando o objeto é uma obra/serviço, os itens do PNCP não descrevem materiais: varre projetos,
    memoriais e orçamentos em busca de insumos do portfólio e registra cada menção com evidência."""
    docs_extraiveis = [d for d in ctx.analise.documentos if d.extraivel and not d.id.startswith("pncp-item")]
    if not docs_extraiveis:
        ctx.analise.lacunas.append("Nenhum anexo com texto extraível para varrer insumos (projetos em .zip/.dwg não foram lidos).")
        return
    for categoria in ctx.empresa.categorias():
        for termo in _TERMOS_INSUMOS.get(categoria, []):
            for r in ctx.indice.buscar(termo, top_k=3, exigir_todas=True):
                if r.trecho.documento_id.startswith("pncp-item"):
                    continue
                ev = ctx.nova_evidencia(r.trecho.documento_id, r.trecho.pagina, r.trecho.texto[:400])
                ctx.analise.insumos_indiretos.append(
                    {"categoria": categoria, "termo": termo, "documento_id": r.trecho.documento_id, "pagina": r.trecho.pagina, "evidencia_id": ev.id, "trecho": r.trecho.texto[:300]}
                )
    vistos = set()
    unicos = []
    for i in ctx.analise.insumos_indiretos:
        chave = (i["documento_id"], i["pagina"], i["categoria"])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(i)
    ctx.analise.insumos_indiretos = unicos
    categorias = sorted({i["categoria"] for i in unicos})
    ctx.evento("varrer_insumos", f"{len(unicos)} menção(ões) a insumos do portfólio em {len(docs_extraiveis)} documento(s): {', '.join(categorias) or 'nenhuma'}")


def executar_analise(
    empresa: Empresa,
    contratacao: Contratacao,
    itens: list[ItemDemanda],
    documentos: list[Documento],
    cfg: Config | None = None,
    on_evento: OnEvento | None = None,
    salvar: bool = True,
) -> Analise:
    cfg = cfg or config
    cfg.garantir_diretorios()
    analise = Analise(
        id=f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}",
        empresa_id=empresa.id,
        contratacao=contratacao,
        itens=[i.model_copy() for i in itens],
    )
    llm = criar_llm_client(cfg, analise.uso_llm)
    analise.modo = f"llm:{llm.provedor}" if llm.disponivel else "deterministico"
    ctx = Contexto(analise=analise, empresa=empresa, indice=IndiceDocumentos(), llm=llm, cfg=cfg, on_evento=on_evento)
    try:
        ctx.evento("carregar_contexto", f"Empresa {empresa.nome} ({len(empresa.produtos)} produtos) × contratação {contratacao.id} ({len(itens)} itens) · modo {analise.modo}")
        _no_coletar_documentos(ctx, [d.model_copy() for d in documentos])
        _no_extrair_itens(ctx)
        relevantes = _no_filtrar_relevantes(ctx)
        _casar(ctx, relevantes)
        afetados = _no_investigador(ctx, relevantes)
        if afetados:
            _casar(ctx, afetados)
        if not relevantes:
            _no_varrer_insumos_indiretos(ctx)
        verificar(ctx)
        analise.qualificacao = qualificar(ctx)
        ctx.evento("qualificar", f"{analise.qualificacao.tipo_oportunidade.value} · prazo {analise.qualificacao.prazo_status} · prioridade {analise.qualificacao.prioridade}")
        resumo, passos, riscos = planejar(ctx)
        analise.qualificacao.proximos_passos = passos
        analise.qualificacao.riscos = riscos
        analise.finalizada_em = datetime.now()
        analise.status = "concluida"
        md = renderizar(analise, empresa, resumo, passos, riscos)
        analise.dossie = Dossie(analise_id=analise.id, titulo=f"Dossiê — {contratacao.orgao_nome} — {contratacao.id}", resumo_executivo=resumo, conteudo_md=md)
        ctx.evento("gerar_dossie", f"Dossiê gerado ({len(md)} caracteres) · custo US$ {analise.uso_llm.custo_usd:.4f}")
    except Exception as exc:  # registra o erro na análise em vez de perder tudo
        analise.status = "erro"
        analise.erro = f"{type(exc).__name__}: {exc}"
        analise.finalizada_em = datetime.now()
        ctx.evento("erro", analise.erro)
        if not salvar:
            raise
    if salvar:
        store.salvar(analise)
    return analise


def executar_caso(diretorio_caso: Path, empresa: Empresa, cfg: Config | None = None, on_evento: OnEvento | None = None, salvar: bool = True) -> Analise:
    """Atalho: executa a análise de um pacote congelado em data/casos/<caso>."""
    from obranexo.connectors.pncp import carregar_caso

    contratacao, itens, documentos = carregar_caso(Path(diretorio_caso))
    return executar_analise(empresa, contratacao, itens, documentos, cfg=cfg, on_evento=on_evento, salvar=salvar)
