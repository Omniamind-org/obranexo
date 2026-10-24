"""Orquestrador da análise de uma licitação.

Uma sequência explícita de nós em Python puro, sem framework: cada nó é uma função que lê e escreve no
estado compartilhado (Contexto). A sequência está declarada como dado em GRAFO (agents/grafo.py), com o
que cada nó lê, escreve e quando roda — é o GRAFO que executa a análise, e é dele que saem a API
(/api/conteudo/grafo), a tela "Sobre" e docs/FLUXO_DO_AGENTE.md.

  carregar_contexto -> coletar_documentos -> extrair_itens -> filtrar_relevantes -> especificador*
  -> casar_com_catalogo -> investigador* -> recasar* -> varrer_insumos_indiretos* -> verificador
  -> qualificar -> planejador -> gerar_dossie          (* condicionais)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from obranexo.agents.contexto import Contexto, OnEvento
from obranexo.agents.especificador import especificar_pelo_tr
from obranexo.agents.extrator import extrair_item, extrair_lotes
from obranexo.agents.grafo import Grafo, No
from obranexo.agents.investigador import investigar
from obranexo.agents.planejador import planejar, qualificar
from obranexo.agents.prompts import VERSAO as VERSAO_PROMPTS
from obranexo.agents.verificador import verificar
from obranexo.catalog.atributos import ATRIBUTOS_INVESTIGAVEIS, natureza
from obranexo.config import Config, config
from obranexo.documents.extract import IndiceDocumentos
from obranexo.dossier.render import renderizar
from obranexo.llm.client import criar_llm_client
from obranexo.models import Analise, Contratacao, Correspondencia, Documento, Dossie, Empresa, ItemDemanda, Requisito, ResultadoItem
from obranexo.observability.trilha import escopo
from obranexo.rules.compare import comparar_item
from obranexo.rules.extrair import inferir_categoria
from obranexo.storage import store

MAX_PRODUTOS_POR_ITEM = 3
# Categorias de item para as quais exigências contratuais (garantia, prazo, amostra) são relevantes
_CATEGORIAS_COM_EXIGENCIAS_GLOBAIS = {"luminaria_publica_led", "luminaria_interna", "refletor_led", "lampada", "rele_fotoeletrico"}


def _expandir_compactados(ctx: Contexto, documentos: list[Documento]) -> list[Documento]:
    """Zips (projetos, atas, planilhas) viram documentos individuais citáveis."""
    from obranexo.documents.formatos import expandir_zip, tipo_arquivo

    saida: list[Documento] = []
    for doc in documentos:
        saida.append(doc)
        if not doc.caminho_local or not Path(doc.caminho_local).exists() or tipo_arquivo(Path(doc.caminho_local)) != "zip":
            continue
        membros = expandir_zip(Path(doc.caminho_local))
        doc.extraivel = False
        doc.nome = f"{doc.nome} (compactado: {len(membros)} arquivo(s) legíveis)"
        for k, membro in enumerate(membros, start=1):
            saida.append(
                Documento(
                    id=f"{doc.id}-z{k}",
                    contratacao_id=doc.contratacao_id,
                    nome=f"{Path(doc.caminho_local).stem} › {membro.name}",
                    tipo_doc=doc.tipo_doc,
                    url_origem=doc.url_origem,
                    caminho_local=str(membro),
                )
            )
        ctx.evento("coletar_documentos", f"{Path(doc.caminho_local).name}: {len(membros)} arquivo(s) extraído(s) do pacote", documento=doc.id)
    return saida


def _no_carregar_contexto(ctx: Contexto) -> None:
    a = ctx.analise
    ctx.evento("carregar_contexto", f"Empresa {ctx.empresa.nome} ({len(ctx.empresa.produtos)} produtos) × contratação {a.contratacao.id} ({len(a.itens)} itens) · modo {a.modo}")


def _no_coletar_documentos(ctx: Contexto) -> None:
    documentos = _expandir_compactados(ctx, [d.model_copy() for d in ctx.documentos_entrada])
    ctx.evento("coletar_documentos", f"Indexando {len(documentos)} documento(s)")
    for doc in documentos:
        ctx.indice.adicionar(doc)
        ctx.analise.documentos.append(doc)
        if doc.caminho_local and "compactado" not in doc.nome:
            ctx.evento(
                "coletar_documentos",
                f"{doc.nome}: {doc.paginas} página(s), {'texto extraído' if doc.extraivel else 'sem texto legível (imagem/digitalizado)'}",
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
    # Lotes de itens por chamada (em paralelo); o processamento item a item segue sequencial e determinístico
    extracoes = extrair_lotes(ctx, ctx.analise.itens)
    for item in ctx.analise.itens:
        item.categoria_inferida = inferir_categoria(item.descricao)
        reqs = extrair_item(ctx, item, f"pncp-item-{item.numero_item}", extracoes.get(item.numero_item))
        ctx.analise.requisitos.extend(reqs)


def _no_filtrar_relevantes(ctx: Contexto) -> None:
    categorias = ctx.empresa.categorias()
    ctx.relevantes = [i for i in ctx.analise.itens if i.categoria_inferida in categorias]
    fora = [i for i in ctx.analise.itens if i.categoria_inferida not in categorias]
    ctx.evento("filtrar_relevantes", f"{len(ctx.relevantes)} item(ns) nas categorias do catálogo; {len(fora)} fora do portfólio")
    for i in fora:
        ctx.evento("filtrar_relevantes", f"Item {i.numero_item} ({i.categoria_inferida}) fora do portfólio", item=i.id)


def _casar(ctx: Contexto, itens: list[ItemDemanda]) -> None:
    ctx.analise.correspondencias = [c for c in ctx.analise.correspondencias if c.item_id not in {i.id for i in itens}]
    for item in itens:
        reqs = [r for r in ctx.analise.requisitos if r.item_id == item.id]
        # Só cláusulas gerais do edital (garantia, prazo, amostra) não provam que o produto serve:
        # sem nenhuma especificação técnica do próprio item, o resultado é INDETERMINADO.
        # Especificação achada pelo Investigador no TR para ESTE item (citação conferida) também conta
        tecnicos = [r for r in reqs if natureza(r.atributo) == "produto" and r.atributo not in ATRIBUTOS_INVESTIGAVEIS
                    and (r.fonte_extracao != "investigador" or r.obrigatorio)]
        candidatos = [p for p in ctx.empresa.produtos if p.categoria == item.categoria_inferida]
        resultados = []
        for p in candidatos:
            resultado, score, detalhes = comparar_item(reqs, p)
            obs = []
            if not tecnicos and resultado in (ResultadoItem.COMPATIVEL, ResultadoItem.PARCIAL):
                resultado, score = ResultadoItem.INDETERMINADO, round(score * 0.5, 4)
                obs.append("A descrição do item não traz especificação técnica verificável; só há exigências gerais do edital.")
            resultados.append(Correspondencia(id=ctx.novo_id("corr"), item_id=item.id, produto_id=p.id, resultado=resultado, detalhes=detalhes, score=score, observacoes=obs))
        ordem = {"COMPATIVEL": 3, "PARCIAL": 2, "INDETERMINADO": 1, "INCOMPATIVEL": 0}
        resultados.sort(key=lambda c: (ordem[c.resultado.value], c.score), reverse=True)
        ctx.analise.correspondencias.extend(resultados[:MAX_PRODUTOS_POR_ITEM])
        melhor = resultados[0].resultado.value if resultados else "sem candidatos"
        ctx.evento("casar_com_catalogo", f"Item {item.numero_item}: {len(candidatos)} candidato(s); melhor = {melhor}", item=item.id)


def _itens_sem_especificacao(ctx: Contexto, itens: list[ItemDemanda], limite: int | None = 8) -> list[ItemDemanda]:
    """Itens do portfólio cuja descrição no PNCP quase não tem especificação técnica ("conforme TR")."""
    pouco = []
    for item in itens:
        tecnicos = [r for r in ctx.analise.requisitos if r.item_id == item.id and natureza(r.atributo) == "produto"
                    and r.atributo not in ATRIBUTOS_INVESTIGAVEIS and r.fonte_extracao != "investigador"]
        if len(tecnicos) < 2:
            pouco.append(item)
    return pouco if limite is None else pouco[:limite]  # no Investigador cada item custa passos do agente


def _precisa_especificador(ctx: Contexto) -> bool:
    return ctx.usar_llm and bool(_itens_sem_especificacao(ctx, ctx.relevantes, limite=None))


def _no_especificador(ctx: Contexto) -> None:
    """Lê no TR, em lote, a especificação dos itens publicados só com o nome (ver agents/especificador.py)."""
    pendentes = _itens_sem_especificacao(ctx, ctx.relevantes, limite=None)
    ctx.analise.requisitos.extend(especificar_pelo_tr(ctx, pendentes))


def _no_casar(ctx: Contexto) -> None:
    _casar(ctx, ctx.relevantes)


def _no_recasar(ctx: Contexto) -> None:
    _casar(ctx, ctx.afetados)


def _no_investigador(ctx: Contexto) -> None:
    ctx.afetados = _investigar(ctx, ctx.relevantes)


def _investigar(ctx: Contexto, itens: list[ItemDemanda]) -> list[ItemDemanda]:
    """Procura nos anexos (1) a especificação técnica de itens com descrição pobre e (2) exigências
    contratuais ausentes nas descrições (garantia, prazo de entrega, amostra...)."""
    alvo = [i for i in itens if i.categoria_inferida in _CATEGORIAS_COM_EXIGENCIAS_GLOBAIS]
    itens_sem_spec = _itens_sem_especificacao(ctx, itens)
    if not alvo and not itens_sem_spec:
        return []
    presentes_em_todos = set(ATRIBUTOS_INVESTIGAVEIS)
    for item in alvo:
        presentes_em_todos &= {r.atributo for r in ctx.analise.requisitos if r.item_id == item.id}
    faltantes = [a for a in ATRIBUTOS_INVESTIGAVEIS if a not in presentes_em_todos] if alvo else []
    if not any(d.extraivel for d in ctx.analise.documentos if not d.id.startswith("pncp-item")):
        ctx.evento("investigador", "Nenhum documento com texto extraível; investigação não é possível.")
        ctx.analise.lacunas.append("Os anexos da contratação não têm texto extraível; exigências do edital (garantia, prazo, amostra) não puderam ser verificadas.")
        return []
    todos = investigar(ctx, faltantes, itens_sem_spec)
    especificos = [r for r in todos if r.item_id != "*"]
    achados = [r for r in todos if r.item_id == "*"]
    afetados: list[ItemDemanda] = []
    for r in especificos:
        ctx.analise.requisitos.append(r)
        item = ctx.analise.item(r.item_id)
        if item and item not in afetados:
            afetados.append(item)
    # As cláusulas gerais do edital valem como obrigatórias para a categoria principal da contratação
    # (a de maior valor); para as demais categorias entram como desejáveis, pois podem referir-se só ao objeto principal.
    valor_por_categoria: dict[str, float] = {}
    for item in alvo:
        valor_por_categoria[item.categoria_inferida] = valor_por_categoria.get(item.categoria_inferida, 0.0) + (item.quantidade or 0) * (item.valor_unit_estimado or 0)
    categoria_principal = max(valor_por_categoria, key=valor_por_categoria.get) if valor_por_categoria else None
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
    ctx.evento("investigador", f"{len(achados)} exigência(s) geral(is) e {len(especificos)} especificação(ões) de item encontrada(s); {len(afetados)} item(ns) reavaliado(s)")
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


def _no_verificar(ctx: Contexto) -> None:
    verificar(ctx)


def _no_qualificar(ctx: Contexto) -> None:
    q = qualificar(ctx)
    ctx.analise.qualificacao = q
    ctx.evento("qualificar", f"{q.tipo_oportunidade.value} · prazo {q.prazo_status} · prioridade {q.prioridade}")


def _no_planejar(ctx: Contexto) -> None:
    resumo, passos, riscos = planejar(ctx)
    assert ctx.analise.qualificacao is not None
    ctx.analise.qualificacao.proximos_passos = passos
    ctx.analise.qualificacao.riscos = riscos
    ctx.plano = (resumo, passos, riscos)


def _no_gerar_dossie(ctx: Contexto) -> None:
    a = ctx.analise
    assert ctx.plano is not None
    resumo, passos, riscos = ctx.plano
    a.finalizada_em = datetime.now()
    a.status = "concluida"
    md = renderizar(a, ctx.empresa, resumo, passos, riscos)
    a.dossie = Dossie(analise_id=a.id, titulo=f"Dossiê — {a.contratacao.orgao_nome} — {a.contratacao.id}", resumo_executivo=resumo, conteudo_md=md)
    u = a.uso_llm
    ctx.evento(
        "gerar_dossie",
        f"Dossiê gerado ({len(md)} caracteres) · {u.chamadas + u.chamadas_cache} chamada(s) de modelo ({u.chamadas_cache} do cache) · custo estimado US$ {u.custo_usd:.4f}",
    )


ESTADO = {
    "descricao": (
        "Os nós não se chamam entre si nem trocam mensagens: cada um lê e escreve no mesmo estado compartilhado, o "
        "Contexto (agents/contexto.py). A parte durável é a Analise, salva em JSON ao fim; o índice dos documentos e "
        "as listas de trabalho (relevantes, afetados, plano) vivem só durante a execução. Toda chamada de modelo feita "
        "por um nó fica ligada à análise na trilha (data/obranexo.db)."
    ),
    "campos": [
        "empresa.produtos", "analise.contratacao", "analise.itens", "analise.documentos", "indice", "analise.requisitos",
        "analise.evidencias", "analise.correspondencias", "analise.conflitos", "analise.lacunas", "analise.revisao_humana",
        "analise.passos_investigacao", "analise.insumos_indiretos", "analise.qualificacao", "analise.dossie",
        "analise.uso_llm", "analise.log", "relevantes", "afetados", "plano",
    ],
}

GRAFO = Grafo(
    estado=ESTADO,
    nos=(
        No("carregar_contexto", "Carregar contexto", "Cruza a empresa com a contratação, define o modo (LLM ou determinístico) e o orçamento de tokens.",
           _no_carregar_contexto, "agents/pipeline.py", le=("empresa.produtos", "analise.contratacao", "analise.itens"), escreve=("analise.modo", "analise.log")),
        No("coletar_documentos", "Coletar documentos", "Extrai o texto por página de PDF, DOCX, XLSX e TXT; abre ZIPs e torna cada arquivo citável; cada item do PNCP vira um documento virtual.",
           _no_coletar_documentos, "agents/pipeline.py · documents/", le=("analise.documentos", "analise.itens"), escreve=("indice", "analise.documentos")),
        No("extrair_itens", "Analista Técnico", "Extrai os requisitos de cada item (potência, tensão, CCT, IP, seção…): regras pt-BR sempre; o modelo complementa em lotes de até 10 itens.",
           _no_extrair_itens, "agents/extrator.py · rules/extrair.py", agente="analista_tecnico", modelo="extracao",
           le=("analise.itens",), escreve=("analise.requisitos", "analise.evidencias", "analise.itens.categoria_inferida")),
        No("filtrar_relevantes", "Filtrar relevantes", "Mantém os itens das categorias que o catálogo cobre; acessórios e o resto saem como fora do portfólio.",
           _no_filtrar_relevantes, "agents/pipeline.py", le=("analise.itens", "empresa.produtos"), escreve=("relevantes",)),
        No("especificador", "Especificador", "Para itens publicados só com o nome, localiza no TR as páginas que tratam deles e lê todas numa chamada; cada atributo entra com trecho conferido.",
           _no_especificador, "agents/especificador.py", agente="especificador", modelo="extracao",
           condicao="há LLM e itens do portfólio com menos de 2 requisitos técnicos", quando=_precisa_especificador,
           le=("relevantes", "analise.requisitos", "indice"), escreve=("analise.requisitos", "analise.evidencias")),
        No("casar_com_catalogo", "Motor de regras", "Compara cada requisito com cada produto da categoria: ATENDE / NÃO ATENDE / INDETERMINADO, agregado por item; guarda os 3 melhores produtos. Nunca usa LLM.",
           _no_casar, "rules/compare.py", le=("relevantes", "analise.requisitos", "empresa.produtos"), escreve=("analise.correspondencias",)),
        No("investigador", "Investigador", "Loop de ferramentas sobre os anexos: especificação de itens ainda pobres e exigências gerais (garantia, prazo, amostra, INMETRO); citação conferida no registro.",
           _no_investigador, "agents/investigador.py", agente="investigador", modelo="agente",
           condicao="há itens do portfólio", quando=lambda ctx: bool(ctx.relevantes),
           le=("relevantes", "analise.requisitos", "indice"), escreve=("analise.requisitos", "analise.evidencias", "analise.passos_investigacao", "analise.lacunas", "afetados")),
        No("recasar", "Motor de regras (de novo)", "Reavalia só os itens que ganharam requisitos com o Investigador.",
           _no_recasar, "rules/compare.py", condicao="o Investigador trouxe requisitos novos", quando=lambda ctx: bool(ctx.afetados),
           le=("afetados", "analise.requisitos", "empresa.produtos"), escreve=("analise.correspondencias",)),
        No("varrer_insumos", "Varrer insumos indiretos", "Quando o objeto é obra ou serviço, procura nos projetos e orçamentos menções a materiais do portfólio, com evidência.",
           _no_varrer_insumos_indiretos, "agents/pipeline.py", condicao="nenhum item do portfólio (obra/serviço)", quando=lambda ctx: not ctx.relevantes,
           le=("indice", "empresa.produtos"), escreve=("analise.insumos_indiretos", "analise.evidencias", "analise.lacunas")),
        No("verificador", "Verificador", "Reconfere todas as citações no documento (similaridade ≥ 90), detecta conflitos entre fontes, atribui confiança; o modelo só escreve o parecer quando há pendências.",
           _no_verificar, "agents/verificador.py · evidence/verify.py", agente="verificador", modelo="agente",
           le=("analise.evidencias", "analise.requisitos", "analise.correspondencias", "indice"), escreve=("analise.evidencias.verificada", "analise.conflitos", "analise.correspondencias.confianca", "analise.revisao_humana")),
        No("qualificar", "Qualificar", "Tipo da oportunidade (publicada, planejada, indireta), comprador provável, prazo e prioridade 0–100 por fórmula.",
           _no_qualificar, "agents/planejador.py", le=("analise.contratacao", "analise.correspondencias", "analise.insumos_indiretos", "empresa.ufs_atendidas"), escreve=("analise.qualificacao",)),
        No("planejador", "Planejador Comercial", "Resumo executivo, próximos passos e riscos em saída estruturada, só a partir dos fatos já verificados.",
           _no_planejar, "agents/planejador.py", agente="planejador", modelo="agente",
           le=("analise.qualificacao", "analise.correspondencias", "analise.conflitos", "analise.lacunas"), escreve=("analise.qualificacao.proximos_passos", "analise.qualificacao.riscos", "plano")),
        No("gerar_dossie", "Gerar dossiê", "Monta o dossiê em Markdown com itens, requisitos, evidências e plano; a análise é salva em JSON.",
           _no_gerar_dossie, "dossier/render.py · storage/store.py", le=("plano", "analise"), escreve=("analise.dossie", "analise.status")),
    ),
)


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
        versao_prompts=VERSAO_PROMPTS,
    )
    llm = criar_llm_client(cfg, analise.uso_llm)
    # Orçamento proporcional ao tamanho: um pregão de 206 itens esgotava o limite fixo já na extração
    llm.orcamento = cfg.orcamento_tokens + 4000 * len(itens)
    analise.modo = f"llm:{llm.provedor}" if llm.disponivel else "deterministico"
    ctx = Contexto(analise=analise, empresa=empresa, indice=IndiceDocumentos(), llm=llm, cfg=cfg, on_evento=on_evento, documentos_entrada=list(documentos))
    # Toda chamada de modelo feita daqui para dentro fica ligada a esta análise na trilha (observability/trilha.py)
    with escopo(origem_tipo="analise", origem_id=analise.id):
        try:
            GRAFO.executar(ctx)
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
