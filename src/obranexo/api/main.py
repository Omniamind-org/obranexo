"""API HTTP do ObraNexo (FastAPI) + servidor do frontend em JavaScript (pasta web/).

Execute:  obranexo servidor        (ou: uvicorn obranexo.api.main:app --reload)
Documentação interativa dos endpoints: http://localhost:8000/api/docs
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from obranexo import __version__
from obranexo.agents.prompts import VERSAO as VERSAO_PROMPTS
from obranexo.api.jobs import jobs
from obranexo.catalog.atributos import ATRIBUTOS
from obranexo.catalog.loader import carregar_catalogo_json, carregar_catalogo_tabela
from obranexo.config import MODELOS_PADRAO, PROVEDORES, config
from obranexo.connectors.pncp import PNCPClient, PNCPError, carregar_caso, listar_casos
from obranexo.models import Analise, Contratacao, Empresa, Produto, ResultadoItem, StatusRevisao
from obranexo.observability import logs
from obranexo.observability.trilha import agregar, escopo, trilha
from obranexo.storage import store

logs.configurar()

app = FastAPI(
    title="ObraNexo API",
    version=__version__,
    description="Inteligência comercial agêntica para contratações públicas — MVP AKCIT Camp 2026.",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

_estado: dict[str, Any] = {"empresa": None}


def empresa_atual() -> Empresa:
    """Catálogo ativo: o último salvo pelo usuário (sobrevive a reinícios) ou o demonstrativo."""
    if _estado["empresa"] is None:
        ativo = store.caminho_catalogo_ativo()
        _estado["empresa"] = carregar_catalogo_json(ativo if ativo.exists() else config.catalogo_demo)
    return _estado["empresa"]


def _definir_empresa(empresa: Empresa) -> None:
    _estado["empresa"] = empresa
    store.salvar_catalogo(empresa)


def _exige_llm(funcionalidade: str) -> None:
    if not config.llm_disponivel:
        raise HTTPException(409, f"{funcionalidade} exige um provedor de LLM configurado (GEMINI_API_KEY, GROQ_API_KEY ou ANTHROPIC_API_KEY no .env)")


# ---------------------------------------------------------------------------
# Serialização
# ---------------------------------------------------------------------------

_ORDEM = {ResultadoItem.COMPATIVEL: 3, ResultadoItem.PARCIAL: 2, ResultadoItem.INDETERMINADO: 1, ResultadoItem.INCOMPATIVEL: 0}


def _resumo_contratacao(c: Contratacao) -> dict[str, Any]:
    return {
        "id": c.id,
        "orgao_nome": c.orgao_nome,
        "orgao_cnpj": c.orgao_cnpj,
        "unidade_nome": c.unidade_nome,
        "municipio": c.municipio,
        "uf": c.uf,
        "modalidade": c.modalidade,
        "numero_compra": c.numero_compra,
        "ano": c.ano,
        "sequencial": c.sequencial,
        "objeto": c.objeto,
        "valor_estimado": c.valor_estimado,
        "valor_homologado": c.valor_homologado,
        "srp": c.srp,
        "data_publicacao": c.data_publicacao.isoformat() if c.data_publicacao else None,
        "data_encerramento_proposta": c.data_encerramento_proposta.isoformat() if c.data_encerramento_proposta else None,
        "situacao": c.situacao,
        "link_oficial": c.link_oficial,
    }


def _casos_por_contratacao() -> dict[str, str]:
    mapa = {}
    for d in listar_casos():
        try:
            c, _, _ = carregar_caso(d)
            mapa[c.id] = d.name
        except Exception:
            continue
    return mapa


def _melhor_por_item(a: Analise) -> dict[str, str]:
    melhor: dict[str, str] = {}
    for c in sorted(a.correspondencias, key=lambda c: (_ORDEM[c.resultado], c.score), reverse=True):
        melhor.setdefault(c.item_id, c.resultado.value)
    return melhor


def _resumo_analise(a: Analise, caso: str | None = None) -> dict[str, Any]:
    melhor = _melhor_por_item(a)
    contagem = {r.value: 0 for r in ResultadoItem}
    for v in melhor.values():
        contagem[v] += 1
    q = a.qualificacao
    return {
        "id": a.id,
        "caso": caso,
        "contratacao": _resumo_contratacao(a.contratacao),
        "status": a.status,
        "erro": a.erro,
        "modo": a.modo,
        "iniciada_em": a.iniciada_em.isoformat(),
        "duracao_s": round(a.duracao_s() or 0, 1),
        "n_itens": len(a.itens),
        "resultados": {**contagem, "FORA_DO_PORTFOLIO": len(a.itens) - len(melhor)},
        "evidencias_total": len(a.evidencias),
        "evidencias_verificadas": sum(e.verificada for e in a.evidencias),
        "lacunas": len(a.lacunas),
        "conflitos": len(a.conflitos),
        "pendencias": len(a.revisao_humana),
        "tipo_oportunidade": q.tipo_oportunidade.value if q else None,
        "prazo_status": q.prazo_status if q else None,
        "prioridade": q.prioridade if q else None,
        "llm": {
            "chamadas": a.uso_llm.chamadas,
            "tokens": a.uso_llm.tokens_entrada + a.uso_llm.tokens_saida,
            "custo_usd": a.uso_llm.custo_usd,
            "modelos": list(a.uso_llm.por_modelo),
        },
        "revisao": a.dossie.status_revisao.value if a.dossie else None,
    }


def _analise_ou_404(analise_id: str) -> Analise:
    a = store.carregar(analise_id)
    if a is None:
        raise HTTPException(404, f"análise '{analise_id}' não encontrada")
    return a


def _caso_dir(nome: str) -> Path:
    destino = (config.dir_casos / nome).resolve()
    if config.dir_casos.resolve() not in destino.parents or not (destino / "contratacao.json").exists():
        raise HTTPException(404, f"caso '{nome}' não encontrado")
    return destino


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@app.get("/api/status", tags=["sistema"])
def status() -> dict[str, Any]:
    """Versão, provedor de LLM, modelos e contadores — usado no rodapé da interface."""
    return {
        "versao": __version__,
        "llm": {
            "provedor": config.llm_provider,
            "disponivel": config.llm_disponivel,
            "modelo_agente": config.model_agente if config.llm_disponivel else None,
            "modelo_extracao": config.model_extracao if config.llm_disponivel else None,
            "modelos_reserva": config.modelos_reserva if config.llm_disponivel else [],
            "provedores": _provedores(),
        },
        "pncp_offline": config.offline,
        "llm_cache": config.llm_cache,
        "versao_prompt": VERSAO_PROMPTS,
        "casos": len(listar_casos()),
        "analises": len(list(config.dir_analises.glob("*.json"))) if config.dir_analises.exists() else 0,
        "empresa": empresa_atual().nome,
    }


def _provedores() -> list[dict[str, Any]]:
    return [
        {"id": p, "configurado": bool(config.chave(p)), "ativo": p == config.llm_provider,
         "modelo_agente": MODELOS_PADRAO[p]["agente"] if p != config.llm_provider else config.model_agente,
         "modelo_extracao": MODELOS_PADRAO[p]["extracao"] if p != config.llm_provider else config.model_extracao}
        for p in PROVEDORES
    ]


class TrocaProvedor(BaseModel):
    provedor: str | None = Field(description="gemini, groq, anthropic ou null (modo determinístico)")


@app.post("/api/config/llm", tags=["sistema"])
def trocar_provedor(corpo: TrocaProvedor) -> dict[str, Any]:
    """Escolhe o provedor de LLM usado pelas próximas análises e prospecções (a chave precisa estar no .env)."""
    try:
        config.usar_provedor(corpo.provedor)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return status()["llm"]


@app.post("/api/config/llm/testar", tags=["sistema"])
def testar_provedor() -> dict[str, Any]:
    """Faz uma chamada mínima ao provedor ativo (sem cache) para conferir chave, rede e modelo."""
    _exige_llm("O teste do provedor")
    from dataclasses import replace

    from obranexo.llm.client import criar_llm_client

    llm = criar_llm_client(replace(config, llm_cache=False))
    inicio = datetime.now()
    try:
        with escopo(agente="teste_provedor", origem_tipo="teste"):
            resposta = llm.texto(config.model_extracao, "Responda só com a palavra pedida.", "Diga: ok", max_tokens=200)
    except Exception as exc:
        return {"ok": False, "provedor": config.llm_provider, "erro": str(exc)[:400]}
    return {"ok": True, "provedor": config.llm_provider, "modelos": list(llm.uso.por_modelo), "resposta": resposta[:80],
            "latencia_s": round((datetime.now() - inicio).total_seconds(), 2)}


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------


@app.get("/api/catalogo", tags=["catálogo"])
def catalogo() -> dict[str, Any]:
    """Empresa ativa e seus produtos (catálogo demonstrativo ou o último enviado)."""
    e = empresa_atual()
    return {
        "empresa": e.model_dump(mode="json", exclude={"produtos"}),
        "categorias": sorted(e.categorias()),
        "produtos": [p.model_dump(mode="json") for p in e.produtos],
    }


@app.post("/api/catalogo", tags=["catálogo"])
async def enviar_catalogo(arquivo: Annotated[UploadFile, File()]) -> dict[str, Any]:
    """Substitui o catálogo ativo por um JSON (formato do demo), CSV ou XLSX."""
    nome = Path(arquivo.filename or "catalogo").name
    sufixo = Path(nome).suffix.lower()
    if sufixo not in {".json", ".csv", ".xlsx", ".xls"}:
        raise HTTPException(400, "formato não suportado: use .json, .csv ou .xlsx")
    config.dir_cache.mkdir(parents=True, exist_ok=True)
    destino = config.dir_cache / f"upload_{datetime.now():%Y%m%d%H%M%S}_{nome}"
    destino.write_bytes(await arquivo.read())
    try:
        empresa = carregar_catalogo_json(destino) if sufixo == ".json" else carregar_catalogo_tabela(destino)
    except Exception as exc:
        raise HTTPException(400, f"não foi possível ler o catálogo: {exc}") from exc
    if not empresa.produtos:
        raise HTTPException(400, "o arquivo não contém produtos")
    _definir_empresa(empresa)
    return {"empresa": empresa.nome, "produtos": len(empresa.produtos)}


@app.delete("/api/catalogo", tags=["catálogo"])
def restaurar_catalogo() -> dict[str, Any]:
    """Volta para o catálogo demonstrativo (descarta o catálogo salvo)."""
    store.remover_catalogo_ativo()
    _estado["empresa"] = carregar_catalogo_json(config.catalogo_demo)
    return {"empresa": _estado["empresa"].nome, "produtos": len(_estado["empresa"].produtos)}


@app.post("/api/catalogo/importar", tags=["catálogo"])
async def importar_ficha_tecnica(
    arquivo: Annotated[UploadFile | None, File()] = None,
    texto: Annotated[str | None, Form()] = None,
    url: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    """Lê uma ficha técnica real (PDF, DOCX, XLSX, texto colado ou página/PDF do fabricante por URL) com o LLM
    e devolve os produtos propostos para revisão. Nada entra no catálogo até POST /api/catalogo/produtos."""
    _exige_llm("A importação de fichas técnicas")
    from obranexo.catalog.importar import importar_ficha
    from obranexo.documents.formatos import baixar_pagina, expandir_zip, extrair_paginas_arquivo, tipo_arquivo
    from obranexo.llm.client import criar_llm_client

    conteudo = (texto or "").strip()
    origem = "texto colado"
    if url and url.strip():
        try:
            pagina = baixar_pagina(url.strip())
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(502, f"não foi possível abrir a página: {exc}") from exc
        if len(pagina) < 300:
            raise HTTPException(422, "a página quase não tem texto (provavelmente é montada por JavaScript). "
                                     "Baixe o PDF da ficha técnica ou cole o texto da página.")
        conteudo = f"{conteudo}\n\nFonte: {url.strip()}\n{pagina}".strip()
        origem = url.strip()
    if arquivo is not None and arquivo.filename:
        nome = Path(arquivo.filename).name
        config.dir_cache.mkdir(parents=True, exist_ok=True)
        destino = config.dir_cache / f"ficha_{datetime.now():%Y%m%d%H%M%S}_{nome}"
        destino.write_bytes(await arquivo.read())
        arquivos = expandir_zip(destino) if tipo_arquivo(destino) == "zip" else [destino]
        partes = ["\n".join(extrair_paginas_arquivo(a)) for a in arquivos]
        conteudo = "\n\n".join(p for p in [conteudo, *partes] if p.strip())
        origem = nome
    if not conteudo:
        raise HTTPException(400, "envie um arquivo com texto legível ou cole o texto da ficha")
    llm = criar_llm_client(config)
    try:
        produtos, avisos = importar_ficha(conteudo, llm, config.model_agente)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"o modelo não conseguiu ler a ficha: {exc}") from exc
    return {"origem": origem, "caracteres": len(conteudo), "produtos": [p.model_dump(mode="json") for p in produtos], "avisos": avisos,
            "llm": {"chamadas": llm.uso.chamadas, "tokens": llm.uso.tokens_entrada + llm.uso.tokens_saida}}


class PedidoProdutos(BaseModel):
    produtos: list[Produto]


@app.post("/api/catalogo/produtos", tags=["catálogo"])
def adicionar_produtos(pedido: PedidoProdutos) -> dict[str, Any]:
    """Adiciona produtos ao catálogo ativo (o mesmo SKU é substituído). O catálogo fica salvo em disco."""
    e = empresa_atual()
    novos = {p.sku: p for p in pedido.produtos}
    mantidos = [p for p in e.produtos if p.sku not in novos]
    _definir_empresa(e.model_copy(update={"produtos": mantidos + list(novos.values())}))
    return {"adicionados": len(novos), "produtos": len(empresa_atual().produtos)}


@app.delete("/api/catalogo/produtos/{sku}", tags=["catálogo"])
def remover_produto(sku: str) -> dict[str, Any]:
    e = empresa_atual()
    restantes = [p for p in e.produtos if p.sku != sku]
    if len(restantes) == len(e.produtos):
        raise HTTPException(404, f"produto '{sku}' não encontrado")
    _definir_empresa(e.model_copy(update={"produtos": restantes}))
    return {"removido": sku, "produtos": len(restantes)}


# ---------------------------------------------------------------------------
# Casos congelados e PNCP
# ---------------------------------------------------------------------------


def _analises_por_caso() -> dict[str, list[dict[str, Any]]]:
    mapa = _casos_por_contratacao()
    por_caso: dict[str, list[dict[str, Any]]] = {}
    for a in store.listar():
        caso = mapa.get(a.contratacao.id)
        if caso:
            por_caso.setdefault(caso, []).append({"id": a.id, "iniciada_em": a.iniciada_em.isoformat(), "status": a.status, "modo": a.modo})
    return por_caso


@app.get("/api/casos", tags=["demandas"])
def casos() -> list[dict[str, Any]]:
    """Pacotes de contratações congelados em data/casos (demo reproduzível)."""
    analises = _analises_por_caso()
    saida = []
    for d in listar_casos():
        c, itens, docs = carregar_caso(d)
        saida.append(
            {
                "nome": d.name,
                "contratacao": _resumo_contratacao(c),
                "n_itens": len(itens),
                "n_documentos": len(docs),
                "n_documentos_baixados": sum(1 for x in docs if x.caminho_local),
                "tem_gabarito": (d / "gabarito.json").exists(),
                "analises": analises.get(d.name, []),
            }
        )
    return saida


@app.get("/api/casos/{nome}", tags=["demandas"])
def caso(nome: str) -> dict[str, Any]:
    d = _caso_dir(nome)
    c, itens, docs = carregar_caso(d)
    return {
        "nome": d.name,
        "contratacao": _resumo_contratacao(c),
        "itens": [i.model_dump(mode="json") for i in itens],
        "documentos": [{"id": x.id, "nome": x.nome, "tipo": x.tipo_doc, "baixado": bool(x.caminho_local), "url_origem": x.url_origem} for x in docs],
        "analises": _analises_por_caso().get(d.name, []),
    }


@app.get("/api/pncp/buscar", tags=["demandas"])
def buscar_pncp(
    uf: str = "GO",
    palavras: str = "lumin,led,refletor,ilumina,material elétrico,material eletrico",
    abertas: bool = True,
    dias: int = Query(30, ge=1, le=365),
    max_paginas: int = Query(5, ge=1, le=20),
) -> dict[str, Any]:
    """Busca contratações (pregão eletrônico) no PNCP e filtra pelo objeto."""
    if config.offline:
        raise HTTPException(503, "modo offline ativo (OBRANEXO_OFFLINE=1)")
    cli = PNCPClient()
    lista_pal = [p.strip() for p in palavras.split(",") if p.strip()]
    achados: list[Contratacao] = []
    pagina, total = 1, 1
    try:
        while pagina <= total and pagina <= max_paginas:
            if abertas:
                lote, total = cli.buscar_propostas_abertas(uf=uf or None, pagina=pagina, horizonte_dias=max(dias, 30))
            else:
                fim = datetime.now()
                lote, total = cli.buscar_publicacoes((fim - timedelta(days=dias)).strftime("%Y%m%d"), fim.strftime("%Y%m%d"), uf=uf or None, pagina=pagina)
            achados += cli.filtrar_por_palavras(lote, lista_pal) if lista_pal else lote
            pagina += 1
    except PNCPError as exc:
        raise HTTPException(502, f"PNCP indisponível: {exc}") from exc
    congelados = _casos_por_contratacao()
    return {
        "paginas_consultadas": pagina - 1,
        "total_paginas": total,
        "resultados": [{**_resumo_contratacao(c), "caso": congelados.get(c.id)} for c in achados],
    }


class PedidoColeta(BaseModel):
    cnpj: str = Field(pattern=r"^\d{14}$")
    ano: int = Field(ge=2000, le=2100)
    sequencial: int = Field(ge=1)
    max_mb: float | None = Field(15, description="anexos maiores ficam listados sem download")


@app.post("/api/pncp/coletar", tags=["demandas"])
def coletar_pncp(pedido: PedidoColeta) -> dict[str, Any]:
    """Baixa itens e anexos de uma contratação e congela em data/casos/<cnpj>_<ano>_<seq>."""
    if config.offline:
        raise HTTPException(503, "modo offline ativo (OBRANEXO_OFFLINE=1)")
    nome = f"{pedido.cnpj}_{pedido.ano}_{pedido.sequencial}"
    try:
        c, itens, docs = PNCPClient().coletar_caso(pedido.cnpj, pedido.ano, pedido.sequencial, config.dir_casos / nome, max_mb=pedido.max_mb)
    except PNCPError as exc:
        raise HTTPException(502, f"PNCP indisponível: {exc}") from exc
    return {"caso": nome, "contratacao": c.id, "itens": len(itens), "documentos": len(docs), "baixados": sum(1 for d in docs if d.caminho_local)}


# ---------------------------------------------------------------------------
# Análises
# ---------------------------------------------------------------------------


class PedidoAnalise(BaseModel):
    caso: str


@app.post("/api/analises", status_code=202, tags=["análises"])
def iniciar_analise(pedido: PedidoAnalise) -> dict[str, Any]:
    """Dispara o fluxo agêntico em segundo plano. Acompanhe em /api/jobs/{id}/eventos (SSE)."""
    job = jobs.iniciar(pedido.caso, _caso_dir(pedido.caso), empresa_atual())
    return job.resumo()


class PedidoProspeccao(BaseModel):
    ufs: list[str] = Field(default_factory=list, description="UFs a prospectar; vazio = UFs atendidas pelo fornecedor")
    horizonte_dias: int = Field(30, ge=3, le=120, description="propostas encerrando nos próximos N dias")
    max_analises: int = Field(2, ge=0, le=5, description="quantas licitações o agente pode analisar a fundo")


@app.post("/api/prospeccoes", status_code=202, tags=["prospecção"])
def iniciar_prospeccao(pedido: PedidoProspeccao) -> dict[str, Any]:
    """Dispara o Agente de Prospecção: ele busca licitações abertas no PNCP, examina itens, escolhe o que
    analisar a fundo e devolve um ranking justificado. Acompanhe em /api/jobs/{id}/eventos."""
    _exige_llm("A prospecção autônoma")
    if config.offline:
        raise HTTPException(503, "modo offline ativo (OBRANEXO_OFFLINE=1): a prospecção consulta o PNCP ao vivo")
    empresa = empresa_atual()
    ufs = [u.upper()[:2] for u in (pedido.ufs or empresa.ufs_atendidas[:1] or ["GO"])]

    def tarefa(job):
        from obranexo.agents.prospector import executar_prospeccao

        p = executar_prospeccao(empresa, ufs, pedido.horizonte_dias, pedido.max_analises, on_evento=job.registrar)
        return p.id, p.status, p.erro

    return jobs.iniciar_tarefa("prospeccao", ",".join(ufs), tarefa).resumo()


def _resumo_prospeccao(p) -> dict[str, Any]:
    return {
        "id": p.id, "status": p.status, "erro": p.erro, "empresa": p.empresa_nome, "parametros": p.parametros,
        "iniciada_em": p.iniciada_em.isoformat(), "duracao_s": round(p.duracao_s() or 0, 1),
        "buscas": len(p.buscas), "candidatos": len(p.candidatos), "analises": sum(1 for c in p.candidatos.values() if c.analise_id),
        "ranking": len(p.ranking), "melhor": p.ranking[0].model_dump(mode="json") if p.ranking else None,
        "llm": {"chamadas": p.uso_llm.chamadas, "tokens": p.uso_llm.tokens_entrada + p.uso_llm.tokens_saida},
    }


@app.get("/api/prospeccoes", tags=["prospecção"])
def prospeccoes() -> list[dict[str, Any]]:
    return [_resumo_prospeccao(p) for p in store.listar_prospeccoes()]


@app.get("/api/prospeccoes/{prospeccao_id}", tags=["prospecção"])
def prospeccao(prospeccao_id: str) -> dict[str, Any]:
    p = store.carregar_prospeccao(prospeccao_id)
    if p is None:
        raise HTTPException(404, "prospecção não encontrada")
    return {"resumo": _resumo_prospeccao(p), "prospeccao": p.model_dump(mode="json")}


# ---------------------------------------------------------------------------
# Assistente (chat)
# ---------------------------------------------------------------------------


def _sessao_ou_404(sessao_id: str):
    from obranexo.agents.assistente import sessoes

    s = sessoes.obter(sessao_id)
    if s is None:
        raise HTTPException(404, "conversa não encontrada (o servidor pode ter reiniciado)")
    return s


@app.post("/api/chat", status_code=201, tags=["assistente"])
def criar_conversa() -> dict[str, Any]:
    """Abre uma conversa com o assistente (usa o provedor de IA e o catálogo ativos)."""
    _exige_llm("O assistente")
    from obranexo.agents.assistente import sessoes

    s = sessoes.criar(empresa_atual())
    return {"sessao_id": s.id, "mensagens": s.mensagens}


@app.get("/api/chat/{sessao_id}", tags=["assistente"])
def conversa(sessao_id: str) -> dict[str, Any]:
    s = _sessao_ou_404(sessao_id)
    return {"sessao_id": s.id, "mensagens": s.mensagens}


class MensagemChat(BaseModel):
    texto: str = Field(min_length=1, max_length=4000)


@app.post("/api/chat/{sessao_id}/mensagens", status_code=202, tags=["assistente"])
def enviar_mensagem(sessao_id: str, corpo: MensagemChat) -> dict[str, Any]:
    """Envia uma pergunta. A resposta chega no evento `fim` de /api/jobs/{id}/eventos (campo `dados.mensagem`);
    os eventos `log` mostram o que o assistente está consultando."""
    s = _sessao_ou_404(sessao_id)

    def tarefa(job):
        job.dados = {"mensagem": s.responder(corpo.texto, on_evento=job.registrar)}
        return s.id, "concluida", None

    return jobs.iniciar_tarefa("chat", s.id, tarefa).resumo()


@app.get("/api/jobs/{job_id}", tags=["análises"])
def job(job_id: str) -> dict[str, Any]:
    j = jobs.obter(job_id)
    if j is None:
        raise HTTPException(404, "job não encontrado")
    return {**j.resumo(), "log": j.eventos}


@app.get("/api/jobs/{job_id}/eventos", tags=["análises"])
async def eventos_job(job_id: str) -> StreamingResponse:
    """Server-Sent Events: `log` para cada passo do fluxo e `fim` com o id da análise."""
    j = jobs.obter(job_id)
    if j is None:
        raise HTTPException(404, "job não encontrado")

    async def gerar():
        enviados = 0
        while True:
            while enviados < len(j.eventos):
                yield f"event: log\ndata: {json.dumps(j.eventos[enviados], ensure_ascii=False)}\n\n"
                enviados += 1
            if j.status != "executando" and enviados >= len(j.eventos):
                yield f"event: fim\ndata: {json.dumps(j.resumo(), ensure_ascii=False)}\n\n"
                return
            await asyncio.sleep(0.25)

    return StreamingResponse(gerar(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/analises", tags=["análises"])
def analises() -> list[dict[str, Any]]:
    mapa = _casos_por_contratacao()
    return [_resumo_analise(a, mapa.get(a.contratacao.id)) for a in store.listar()]


@app.get("/api/analises/{analise_id}", tags=["análises"])
def analise(analise_id: str) -> dict[str, Any]:
    """Análise completa (itens, requisitos, correspondências, evidências, qualificação, dossiê)."""
    a = _analise_ou_404(analise_id)
    empresa = empresa_atual()
    ids = {c.produto_id for c in a.correspondencias}
    produtos = {p.id: {"sku": p.sku, "nome": p.nome, "categoria": p.categoria} for p in empresa.produtos if p.id in ids}
    for pid in ids - set(produtos):
        produtos[pid] = {"sku": pid, "nome": "(produto fora do catálogo ativo)", "categoria": None}
    caso_nome = _casos_por_contratacao().get(a.contratacao.id)
    usados = {r.atributo for r in a.requisitos}
    rotulos = {k: {"rotulo": m["rotulo"], "unidade": m.get("unidade")} for k, m in ATRIBUTOS.items() if k in usados}
    return {"resumo": _resumo_analise(a, caso_nome), "analise": a.model_dump(mode="json"), "produtos": produtos, "atributos": rotulos}


@app.get("/api/analises/{analise_id}/dossie.md", tags=["análises"], response_class=PlainTextResponse)
def dossie_md(analise_id: str, download: bool = False) -> PlainTextResponse:
    a = _analise_ou_404(analise_id)
    if not a.dossie:
        raise HTTPException(409, "análise sem dossiê")
    headers = {"Content-Disposition": f'attachment; filename="dossie_{a.id}.md"'} if download else {}
    return PlainTextResponse(a.dossie.conteudo_md, media_type="text/markdown; charset=utf-8", headers=headers)


class PedidoRevisao(BaseModel):
    status: StatusRevisao
    comentario: str = ""


@app.patch("/api/analises/{analise_id}/revisao", tags=["análises"])
def revisar(analise_id: str, pedido: PedidoRevisao) -> dict[str, Any]:
    """Registra a decisão humana sobre o dossiê (feedback para o benchmark)."""
    a = _analise_ou_404(analise_id)
    if not a.dossie:
        raise HTTPException(409, "análise sem dossiê")
    a.dossie.status_revisao = pedido.status
    a.dossie.comentario_usuario = pedido.comentario
    store.salvar(a)
    return {"id": a.id, "revisao": a.dossie.status_revisao.value, "comentario": a.dossie.comentario_usuario}


def _documento_local(a: Analise, documento_id: str) -> tuple[Any, Path | None]:
    doc = next((d for d in a.documentos if d.id == documento_id), None)
    if doc is None:
        raise HTTPException(404, "documento não encontrado")
    if not doc.caminho_local:
        return doc, None
    caminho = Path(doc.caminho_local).resolve()
    if config.dir_casos.resolve() not in caminho.parents or not caminho.exists():
        return doc, None
    return doc, caminho


@app.get("/api/analises/{analise_id}/evidencias/{evidencia_id}", tags=["análises"])
def evidencia(analise_id: str, evidencia_id: str) -> dict[str, Any]:
    """Trecho citado + texto da página de origem, para conferência humana."""
    a = _analise_ou_404(analise_id)
    ev = a.evidencia(evidencia_id)
    if ev is None:
        raise HTTPException(404, "evidência não encontrada")
    doc, caminho = _documento_local(a, ev.documento_id)
    texto = None
    if doc.id.startswith("pncp-item"):
        numero = int(doc.id.rsplit("-", 1)[-1])
        item = next((i for i in a.itens if i.numero_item == numero), None)
        texto = item.descricao if item else None
    elif caminho and ev.pagina:
        from obranexo.documents.extract import extrair_paginas

        paginas = extrair_paginas(caminho)
        if 1 <= ev.pagina <= len(paginas):
            texto = paginas[ev.pagina - 1]
    return {
        "evidencia": ev.model_dump(mode="json"),
        "documento": {"id": doc.id, "nome": doc.nome, "tipo": doc.tipo_doc, "url_origem": doc.url_origem, "tem_arquivo": caminho is not None,
                      "eh_pdf": bool(caminho and caminho.suffix.lower() == ".pdf")},
        "texto_pagina": texto,
    }


@app.get("/api/analises/{analise_id}/documentos/{documento_id}/arquivo", tags=["análises"])
def arquivo_documento(analise_id: str, documento_id: str) -> FileResponse:
    """Arquivo original do anexo (PDF), servido a partir do pacote congelado."""
    a = _analise_ou_404(analise_id)
    _, caminho = _documento_local(a, documento_id)
    if caminho is None:
        raise HTTPException(404, "arquivo não disponível localmente")
    media = "application/pdf" if caminho.suffix.lower() == ".pdf" else "application/octet-stream"
    return FileResponse(caminho, media_type=media, filename=caminho.name, content_disposition_type="inline")


@app.get("/api/metricas", tags=["análises"])
def metricas() -> dict[str, Any]:
    """Agregados de todas as análises registradas."""
    lista = analises()
    concluidas = [x for x in lista if x["status"] == "concluida"]
    ev_total = sum(x["evidencias_total"] for x in concluidas)
    ev_ok = sum(x["evidencias_verificadas"] for x in concluidas)
    beneficio = Path(config.raiz / "docs" / "benchmark_resultado.json")
    return {
        "analises": len(lista),
        "concluidas": len(concluidas),
        "rastreabilidade": round(ev_ok / ev_total, 4) if ev_total else None,
        "duracao_media_s": round(sum(x["duracao_s"] for x in concluidas) / len(concluidas), 1) if concluidas else None,
        "custo_total_usd": round(sum(x["llm"]["custo_usd"] for x in lista), 4),
        "chamadas_llm": sum(x["llm"]["chamadas"] for x in lista),
        "tokens": sum(x["llm"]["tokens"] for x in lista),
        "revisoes": {s.value: sum(1 for x in lista if x["revisao"] == s.value) for s in StatusRevisao},
        "benchmark": json.loads(beneficio.read_text(encoding="utf-8")).get("resumo") if beneficio.exists() else None,
        "lista": lista,
    }


@app.get("/api/metricas/llm", tags=["análises"])
def metricas_llm() -> dict[str, Any]:
    """Agregados de todas as chamadas de modelo (análises, prospecções, chat): custo, latência, cache, reserva e erro,
    por agente e por modelo — a trilha de observability/trilha.py vista de cima."""
    resumo = trilha.resumo()
    resumo["precos_usd"] = {modelo: list(preco) for modelo, preco in config.precos_usd.items()}
    resumo["nota"] = (
        "Custo estimado pela tabela oficial de preços (US$ por 1M tokens) a partir dos tokens que cada API devolve, "
        "com o raciocínio cobrado como saída; no nível gratuito do Gemini e do Groq a cobrança real é zero."
    )
    return resumo


@app.get("/api/analises/{analise_id}/chamadas", tags=["análises"])
def chamadas_llm(analise_id: str) -> dict[str, Any]:
    """Trilha de chamadas de modelo da análise: quem chamou, que modelo respondeu, tokens, custo, latência, cache e erro."""
    _analise_ou_404(analise_id)
    chamadas = trilha.listar(analise_id)
    return {"chamadas": chamadas, "resumo": agregar(chamadas)}


@app.get("/api/conteudo/fluxo", tags=["sistema"], response_class=PlainTextResponse)
def conteudo_fluxo() -> PlainTextResponse:
    """Documentação do fluxo dos agentes (Markdown), exibida na página 'Como funciona'."""
    return PlainTextResponse((config.raiz / "docs" / "fluxo_agentes.md").read_text(encoding="utf-8"), media_type="text/markdown; charset=utf-8")


# ---------------------------------------------------------------------------
# Frontend estático (montado por último para não sombrear /api)
# ---------------------------------------------------------------------------

if (config.raiz / "images").exists():
    app.mount("/images", StaticFiles(directory=config.raiz / "images"), name="images")

if config.dir_web.exists():
    app.mount("/", StaticFiles(directory=config.dir_web, html=True), name="web")

