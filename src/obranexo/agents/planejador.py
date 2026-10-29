"""Qualificação comercial (regras) + Agente Planejador Comercial (LLM opcional)."""

from __future__ import annotations

import json
import re
from datetime import datetime

from pydantic import BaseModel, Field

from obranexo.agents.contexto import Contexto
from obranexo.agents.prompts import SYSTEM_PLANEJADOR, VERSAO
from obranexo.models import Qualificacao, ResultadoItem, TipoOportunidade
from obranexo.observability.trilha import escopo

# Pesos da prioridade (0-100). O prazo pesa mais que a cobertura: uma licitação aberta é uma venda possível agora,
# uma encerrada no máximo uma ata para aderir. Uma encerrada chega no máximo a 55 (tudo compatível, com registro
# de preços); uma aberta com 40% do valor compatível já empata.
PESO_COBERTURA = 0.5  # fração do valor estimado em itens compatíveis/parciais
PESO_INDETERMINADO = 0.15  # fração em itens que dependem de confirmar a especificação
BONUS_PRAZO_ABERTO = 35
BONUS_ENCERRADA_SRP = 5  # registro de preços: a ata pode permitir adesão
FATOR_VENDA_INDIRETA = 0.6
FATOR_FORA_DA_UF = 0.7

_PALAVRAS_OBRA = r"\b(obra|obras|execu[cç][aã]o|constru[cç][aã]o|reforma|amplia[cç][aã]o|engenharia|empreitada|remanescente)\b"
_PALAVRAS_SERVICO = r"\b(presta[cç][aã]o de servi[cç]os?|loca[cç][aã]o|manuten[cç][aã]o)\b"


def classificar_tipo(objeto: str, fonte: str = "PNCP") -> tuple[TipoOportunidade, str, str]:
    """Retorna (tipo, comprador provável, justificativa)."""
    o = objeto.lower()
    if fonte.upper() == "PCA":
        return TipoOportunidade.PLANEJADA, "Órgão (compra ainda não publicada)", "Registro vindo de Plano de Contratações Anual: demanda prevista, sujeita a alteração."
    if re.search(_PALAVRAS_OBRA, o) and not re.search(r"\baquisi[cç][aã]o\b.*\b(lumin|material|equipamento)", o):
        return (
            TipoOportunidade.INDIRETA,
            "Construtora/empresa vencedora da obra (não o órgão)",
            "O objeto é a execução de uma obra ou serviço de engenharia: o órgão contrata a execução integral; "
            "os materiais serão comprados pela empresa contratada. A venda, se houver, é indireta.",
        )
    if re.search(_PALAVRAS_SERVICO, o) and not re.search(r"\b(fornecimento|aquisi[cç][aã]o)\b", o):
        return (
            TipoOportunidade.INDIRETA,
            "Prestadora do serviço (não o órgão)",
            "O objeto é prestação de serviço/locação; materiais entram como insumo da prestadora.",
        )
    return TipoOportunidade.PUBLICADA, "Órgão contratante (venda direta)", "Processo de contratação publicado oficialmente para aquisição/fornecimento de bens."


def status_prazo(encerramento: datetime | None, agora: datetime | None = None) -> tuple[str, str]:
    agora = agora or datetime.now()
    if encerramento is None:
        return "DESCONHECIDA", "Data de encerramento de propostas não informada na fonte."
    if encerramento.replace(tzinfo=None) >= agora:
        dias = (encerramento.replace(tzinfo=None) - agora).days
        return "ABERTA", f"Propostas abertas até {encerramento:%d/%m/%Y %H:%M} (faltam {dias} dia(s))."
    return "ENCERRADA", f"Recebimento de propostas encerrado em {encerramento:%d/%m/%Y}. Acompanhar resultado/ata e próximas edições."


def _melhor_por_item(ctx: Contexto) -> dict[str, ResultadoItem]:
    ordem = {ResultadoItem.COMPATIVEL: 3, ResultadoItem.PARCIAL: 2, ResultadoItem.INDETERMINADO: 1, ResultadoItem.INCOMPATIVEL: 0}
    melhor: dict[str, ResultadoItem] = {}
    for c in ctx.analise.correspondencias:
        atual = melhor.get(c.item_id)
        if atual is None or ordem[c.resultado] > ordem[atual]:
            melhor[c.item_id] = c.resultado
    return melhor


def qualificar(ctx: Contexto) -> Qualificacao:
    a = ctx.analise
    ct = a.contratacao
    tipo, comprador, just_tipo = classificar_tipo(ct.objeto, ct.fonte)
    prazo, prazo_obs = status_prazo(ct.data_encerramento_proposta)
    melhor = _melhor_por_item(ctx)

    valor_total = valor_compat = valor_indet = 0.0
    for item in a.itens:
        v = (item.quantidade or 0) * (item.valor_unit_estimado or 0)
        valor_total += v
        r = melhor.get(item.id)
        if r in (ResultadoItem.COMPATIVEL, ResultadoItem.PARCIAL):
            valor_compat += v
        elif r == ResultadoItem.INDETERMINADO:
            valor_indet += v
    cobertura = (valor_compat / valor_total) if valor_total else 0.0
    cobertura_indet = (valor_indet / valor_total) if valor_total else 0.0

    prioridade = 100 * (PESO_COBERTURA * cobertura + PESO_INDETERMINADO * cobertura_indet)
    just = [f"{cobertura:.0%} do valor estimado em itens compatíveis/parciais"]
    if cobertura_indet:
        just.append(f"{cobertura_indet:.0%} indeterminado")
    if prazo == "ABERTA":
        prioridade += BONUS_PRAZO_ABERTO
        just.append("prazo de propostas aberto")
    elif prazo == "ENCERRADA":
        prioridade += BONUS_ENCERRADA_SRP if ct.srp else 0
        just.append("prazo encerrado" + (" (registro de preços: ata pode permitir adesão/novas contratações)" if ct.srp else ""))
    if tipo == TipoOportunidade.INDIRETA:
        prioridade *= FATOR_VENDA_INDIRETA
        just.append("venda indireta (comprador é a contratada)")
        if a.insumos_indiretos:
            categorias = {i["categoria"] for i in a.insumos_indiretos}
            prioridade += min(30.0, 6.0 * len(categorias))
            just.append(f"{len(a.insumos_indiretos)} menção(ões) a {len(categorias)} categoria(s) do portfólio nos projetos")
    uf_ok = not ctx.empresa.ufs_atendidas or (ct.uf in ctx.empresa.ufs_atendidas)
    if not uf_ok:
        prioridade *= FATOR_FORA_DA_UF
        just.append(f"UF {ct.uf} fora das regiões atendidas")
    prioridade = round(min(100.0, prioridade), 1)

    riscos: list[str] = []
    if prazo == "ENCERRADA":
        riscos.append("Prazo de propostas já encerrado: a oportunidade direta neste certame passou; vale para ata (SRP), adesões e próximas licitações do órgão.")
    if tipo == TipoOportunidade.INDIRETA:
        riscos.append("Comprador real é a empresa contratada para a obra/serviço; é preciso identificá-la na ata/contrato.")
    if a.conflitos:
        riscos.append(f"{len(a.conflitos)} conflito(s) entre fontes/extrações exigem conferência manual.")
    if a.lacunas:
        riscos.append(f"{len(a.lacunas)} informação(ões) não localizada(s) nos documentos (ver lacunas).")
    incompat = [i for i, r in melhor.items() if r == ResultadoItem.INCOMPATIVEL]
    if incompat:
        riscos.append(f"{len(incompat)} item(ns) sem produto compatível no catálogo atual.")
    if not uf_ok:
        riscos.append("Logística: UF fora da área de atendimento declarada.")

    passos: list[str] = []
    if prazo == "ABERTA":
        passos.append(f"Preparar proposta e documentação de habilitação antes de {ct.data_encerramento_proposta:%d/%m/%Y}.")
    if ct.link_oficial:
        passos.append(f"Conferir no PNCP a situação atual e os anexos: {ct.link_oficial}")
    if ct.srp:
        passos.append("Registro de preços: verificar validade da ata, fornecedores registrados e possibilidade de adesão (carona) por outros órgãos.")
    if tipo == TipoOportunidade.INDIRETA:
        passos.append("Localizar a empresa vencedora (ata/contrato) e apresentar o portfólio diretamente ao seu setor de suprimentos.")
        if a.insumos_indiretos:
            passos.append("Levantar quantidades e especificações dos insumos citados nos projetos/orçamento (ver seção 4b) antes do contato.")
    indets = [i for i, r in melhor.items() if r == ResultadoItem.INDETERMINADO]
    if indets:
        passos.append("Completar no catálogo os atributos indeterminados (ver tabela) para fechar a avaliação técnica.")
    if incompat:
        passos.append("Avaliar se vale homologar/adquirir um produto que atenda aos requisitos não atendidos (ver tabela).")
    if a.revisao_humana:
        passos.append("Revisar as pendências apontadas pelo Verificador antes de qualquer contato comercial.")
    passos.append("Registrar a decisão (seguir / descartar / acompanhar) e o responsável.")

    return Qualificacao(
        tipo_oportunidade=tipo,
        comprador_provavel=comprador,
        justificativa_tipo=just_tipo,
        prazo_status=prazo,
        prazo_observacao=prazo_obs,
        prioridade=prioridade,
        justificativa_prioridade="; ".join(just) + ".",
        riscos=riscos,
        proximos_passos=passos,
    )


class PlanoComercial(BaseModel):
    resumo_executivo: str
    proximos_passos: list[str] = Field(default_factory=list)
    riscos: list[str] = Field(default_factory=list)


def resumo_executivo_regras(ctx: Contexto) -> str:
    a = ctx.analise
    q = a.qualificacao
    melhor = _melhor_por_item(ctx)
    n = len(a.itens)
    compat = sum(1 for r in melhor.values() if r == ResultadoItem.COMPATIVEL)
    parcial = sum(1 for r in melhor.values() if r == ResultadoItem.PARCIAL)
    indet = sum(1 for r in melhor.values() if r == ResultadoItem.INDETERMINADO)
    incompat = sum(1 for r in melhor.values() if r == ResultadoItem.INCOMPATIVEL)
    fora = n - len(melhor)
    partes = [
        f"A contratação {a.contratacao.id} ({a.contratacao.orgao_nome}, {a.contratacao.municipio}/{a.contratacao.uf}) tem {n} item(ns); "
        f"{compat} compatível(is), {parcial} parcial(is), {indet} indeterminado(s), {incompat} incompatível(is) e {fora} fora do portfólio.",
        f"Classificação: {q.tipo_oportunidade.value} — comprador provável: {q.comprador_provavel}.",
        q.prazo_observacao,
        f"Prioridade {q.prioridade:.0f}/100 ({q.justificativa_prioridade})",
    ]
    return " ".join(partes)


def planejar(ctx: Contexto) -> tuple[str, list[str], list[str]]:
    """Retorna (resumo executivo, próximos passos, riscos)."""
    a = ctx.analise
    q = a.qualificacao
    assert q is not None
    resumo = resumo_executivo_regras(ctx)
    if not ctx.usar_llm:
        return resumo, q.proximos_passos, q.riscos
    try:
        melhor = _melhor_por_item(ctx)
        fatos = {
            "contratacao": {
                "id": a.contratacao.id, "orgao": a.contratacao.orgao_nome, "municipio": a.contratacao.municipio, "uf": a.contratacao.uf,
                "objeto": a.contratacao.objeto, "modalidade": a.contratacao.modalidade, "valor_estimado": a.contratacao.valor_estimado,
                "srp": a.contratacao.srp, "situacao": a.contratacao.situacao,
                "encerramento_propostas": a.contratacao.data_encerramento_proposta.isoformat() if a.contratacao.data_encerramento_proposta else None,
            },
            "qualificacao_por_regras": q.model_dump(mode="json"),
            "itens": [
                {"numero": i.numero_item, "descricao": i.descricao[:200], "quantidade": i.quantidade, "valor_unit": i.valor_unit_estimado,
                 "melhor_resultado": melhor.get(i.id, "FORA_DO_PORTFOLIO")}
                for i in a.itens
            ],
            "correspondencias": [
                {"item": c.item_id.split("#")[-1], "produto": c.produto_id, "resultado": c.resultado, "confianca": c.confianca,
                 "nao_atendidos": [d.justificativa for d in c.detalhes if d.resultado == "NAO_ATENDE"][:5],
                 "indeterminados": [d.justificativa for d in c.detalhes if d.resultado == "INDETERMINADO"][:5]}
                for c in a.correspondencias
            ],
            "lacunas": a.lacunas, "conflitos": [c.descricao for c in a.conflitos], "revisao_humana": a.revisao_humana[:8],
            "empresa": {"nome": ctx.empresa.nome, "ufs_atendidas": ctx.empresa.ufs_atendidas},
            "data_hoje": datetime.now().strftime("%d/%m/%Y"),
        }
        with escopo(agente="planejador", versao_prompt=VERSAO):
            plano = ctx.llm.extrair(
                ctx.cfg.model_agente,
                SYSTEM_PLANEJADOR,
                "Fatos verificados da análise (JSON):\n" + json.dumps(fatos, ensure_ascii=False, indent=1, default=str),
                PlanoComercial,
            )
        ctx.evento("planejador", "Plano comercial gerado pelo Agente Planejador", modelo=ctx.cfg.model_agente)
        passos = plano.proximos_passos or q.proximos_passos
        riscos = list(dict.fromkeys(plano.riscos + q.riscos))
        return plano.resumo_executivo or resumo, passos, riscos
    except Exception as exc:
        ctx.evento("planejador", f"Planejador LLM indisponível ({exc}); usando plano por regras.")
        return resumo, q.proximos_passos, q.riscos
