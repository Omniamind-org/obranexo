"""Modelos de dados do ObraNexo (Pydantic v2).

Convenção: tudo que o sistema conclui aponta para uma Evidencia. Sem evidência,
o resultado é INDETERMINADO — nunca uma afirmação.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enumerações
# ---------------------------------------------------------------------------


class TipoAtributo(StrEnum):
    NUMERO = "numero"
    FAIXA = "faixa"
    ENUM = "enum"
    TEXTO = "texto"
    BOOLEANO = "booleano"


class Operador(StrEnum):
    IGUAL = "="
    MAIOR_IGUAL = ">="
    MENOR_IGUAL = "<="
    ENTRE = "entre"
    CONTEM = "contem"
    VERDADEIRO = "verdadeiro"


class ResultadoRequisito(StrEnum):
    ATENDE = "ATENDE"
    NAO_ATENDE = "NAO_ATENDE"
    INDETERMINADO = "INDETERMINADO"


class ResultadoItem(StrEnum):
    COMPATIVEL = "COMPATIVEL"
    PARCIAL = "PARCIAL"
    INCOMPATIVEL = "INCOMPATIVEL"
    INDETERMINADO = "INDETERMINADO"


class TipoOportunidade(StrEnum):
    PUBLICADA = "PUBLICADA"
    PLANEJADA = "PLANEJADA"
    INDIRETA = "INDIRETA_POTENCIAL"
    INFERIDA = "INFERIDA"


class Confianca(StrEnum):
    ALTA = "alta"
    MEDIA = "media"
    BAIXA = "baixa"


class StatusRevisao(StrEnum):
    PENDENTE = "PENDENTE"
    APROVADO = "APROVADO"
    REJEITADO = "REJEITADO"


# ---------------------------------------------------------------------------
# Catálogo do fornecedor
# ---------------------------------------------------------------------------


class Atributo(BaseModel):
    valor: Any
    unidade: str | None = None
    tipo: TipoAtributo = TipoAtributo.NUMERO


class Produto(BaseModel):
    id: str
    sku: str
    nome: str
    categoria: str
    subcategoria: str | None = None
    # Identificação comercial exigida nas propostas (os editais pedem marca e modelo de cada item)
    fabricante: str | None = None
    marca: str | None = None
    modelo: str | None = None
    descricao: str = ""
    atributos: dict[str, Atributo] = Field(default_factory=dict)
    normas: list[str] = Field(default_factory=list)
    certificacoes: list[str] = Field(default_factory=list)
    preco_ref: float | None = None
    prazo_entrega_dias: int | None = None
    estoque: int | None = None


class Empresa(BaseModel):
    id: str
    nome: str
    cnpj: str | None = None
    # Dados do cabeçalho e da assinatura da proposta de preços (vazios viram "[preencher]" no documento)
    razao_social: str | None = None
    endereco: str | None = None
    telefone: str | None = None
    email: str | None = None
    representante: str | None = None
    representante_cargo: str | None = None
    dados_bancarios: str | None = None
    ufs_atendidas: list[str] = Field(default_factory=list)
    raio_km: int | None = None
    observacoes: str = ""
    produtos: list[Produto] = Field(default_factory=list)

    def categorias(self) -> set[str]:
        return {p.categoria for p in self.produtos}


# ---------------------------------------------------------------------------
# Demandas públicas
# ---------------------------------------------------------------------------


class Contratacao(BaseModel):
    id: str  # numeroControlePNCP
    fonte: str = "PNCP"
    orgao_cnpj: str
    orgao_nome: str
    unidade_nome: str | None = None
    uf: str | None = None
    municipio: str | None = None
    modalidade: str | None = None
    numero_compra: str | None = None
    ano: int
    sequencial: int
    objeto: str
    valor_estimado: float | None = None
    valor_homologado: float | None = None
    srp: bool = False
    data_publicacao: datetime | None = None
    data_abertura_proposta: datetime | None = None
    data_encerramento_proposta: datetime | None = None
    situacao: str | None = None
    link_oficial: str | None = None
    link_sistema_origem: str | None = None
    bruto: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @property
    def link_pncp(self) -> str:
        return f"https://pncp.gov.br/app/editais/{self.orgao_cnpj}/{self.ano}/{self.sequencial}"


class Documento(BaseModel):
    id: str
    contratacao_id: str
    nome: str
    tipo_doc: str | None = None
    url_origem: str | None = None
    sha256: str | None = None
    caminho_local: str | None = None
    paginas: int = 0
    extraivel: bool = True


class Trecho(BaseModel):
    id: str
    documento_id: str
    pagina: int
    ordem: int
    texto: str


class ItemDemanda(BaseModel):
    id: str
    contratacao_id: str
    numero_item: int
    descricao: str
    quantidade: float | None = None
    unidade: str | None = None
    valor_unit_estimado: float | None = None
    categoria_inferida: str | None = None
    situacao: str | None = None


# ---------------------------------------------------------------------------
# Evidências, requisitos e correspondências
# ---------------------------------------------------------------------------


class Evidencia(BaseModel):
    id: str
    documento_id: str
    pagina: int | None = None
    trecho_literal: str
    verificada: bool = False
    score_match: float | None = None


class Requisito(BaseModel):
    id: str
    item_id: str
    atributo: str
    operador: Operador
    valor: Any
    unidade: str | None = None
    obrigatorio: bool = True
    texto_origem: str = ""
    evidencia_id: str | None = None
    fonte_extracao: str = "regras"  # regras | llm | investigador


class DetalheRequisito(BaseModel):
    requisito_id: str
    atributo: str
    resultado: ResultadoRequisito
    justificativa: str
    valor_exigido: Any = None
    valor_produto: Any = None


class Correspondencia(BaseModel):
    id: str
    item_id: str
    produto_id: str
    resultado: ResultadoItem
    detalhes: list[DetalheRequisito] = Field(default_factory=list)
    score: float = 0.0
    confianca: Confianca = Confianca.MEDIA
    observacoes: list[str] = Field(default_factory=list)


class Conflito(BaseModel):
    atributo: str
    item_id: str
    valores: list[dict[str, Any]]
    descricao: str


# ---------------------------------------------------------------------------
# Análise e dossiê
# ---------------------------------------------------------------------------


class EventoLog(BaseModel):
    ts: datetime = Field(default_factory=datetime.now)
    no: str
    mensagem: str
    dados: dict[str, Any] = Field(default_factory=dict)


class UsoLLM(BaseModel):
    """Consumo de modelos numa análise. Os tokens vêm da resposta de cada API (usage); o custo é estimado
    pela tabela oficial de preços em config.precos_usd — no nível gratuito a cobrança real é zero."""

    chamadas: int = 0  # chamadas que chegaram ao provedor (cache não conta)
    chamadas_cache: int = 0  # respostas reaproveitadas do cache em disco
    chamadas_reserva: int = 0  # respondidas pelo modelo reserva, não pelo pedido
    tokens_entrada: int = 0
    tokens_saida: int = 0
    tokens_raciocinio: int = 0  # "thinking": cobrados como saída, mas não aparecem na resposta
    tokens_cache_leitura: int = 0
    custo_usd: float = 0.0
    latencia_ms: int = 0  # soma do tempo de espera pelo provedor
    por_modelo: dict[str, dict[str, int]] = Field(default_factory=dict)


class Qualificacao(BaseModel):
    tipo_oportunidade: TipoOportunidade
    comprador_provavel: str
    justificativa_tipo: str
    prazo_status: str  # ABERTA | ENCERRADA | DESCONHECIDA
    prazo_observacao: str
    prioridade: float
    justificativa_prioridade: str
    riscos: list[str] = Field(default_factory=list)
    proximos_passos: list[str] = Field(default_factory=list)


class Dossie(BaseModel):
    analise_id: str
    titulo: str
    resumo_executivo: str
    conteudo_md: str
    status_revisao: StatusRevisao = StatusRevisao.PENDENTE
    comentario_usuario: str = ""


class Analise(BaseModel):
    id: str
    empresa_id: str
    contratacao: Contratacao
    status: str = "iniciada"
    modo: str = "deterministico"  # deterministico | llm
    iniciada_em: datetime = Field(default_factory=datetime.now)
    finalizada_em: datetime | None = None
    documentos: list[Documento] = Field(default_factory=list)
    itens: list[ItemDemanda] = Field(default_factory=list)
    requisitos: list[Requisito] = Field(default_factory=list)
    evidencias: list[Evidencia] = Field(default_factory=list)
    correspondencias: list[Correspondencia] = Field(default_factory=list)
    conflitos: list[Conflito] = Field(default_factory=list)
    lacunas: list[str] = Field(default_factory=list)
    revisao_humana: list[str] = Field(default_factory=list)
    passos_investigacao: list[dict[str, Any]] = Field(default_factory=list)
    # Obras/serviços (oportunidade INDIRETA): menções a insumos do portfólio achadas nos projetos/orçamentos
    insumos_indiretos: list[dict[str, Any]] = Field(default_factory=list)
    qualificacao: Qualificacao | None = None
    dossie: Dossie | None = None
    uso_llm: UsoLLM = Field(default_factory=UsoLLM)
    log: list[EventoLog] = Field(default_factory=list)
    erro: str | None = None
    versao_prompts: str = "v0.1"

    def evidencia(self, evidencia_id: str | None) -> Evidencia | None:
        if not evidencia_id:
            return None
        return next((e for e in self.evidencias if e.id == evidencia_id), None)

    def item(self, item_id: str) -> ItemDemanda | None:
        return next((i for i in self.itens if i.id == item_id), None)

    def duracao_s(self) -> float | None:
        if not self.finalizada_em:
            return None
        return (self.finalizada_em - self.iniciada_em).total_seconds()


# ---------------------------------------------------------------------------
# Prospecção (agente autônomo que escolhe as oportunidades)
# ---------------------------------------------------------------------------


class CandidatoProspeccao(BaseModel):
    contratacao: dict[str, Any]
    itens_vistos: bool = False
    analise_id: str | None = None
    resumo_analise: dict[str, Any] | None = None


class ItemRanking(BaseModel):
    contratacao_id: str
    nota: float
    justificativa: str
    analise_id: str | None = None
    contratacao: dict[str, Any] | None = None


class Prospeccao(BaseModel):
    id: str
    empresa_id: str
    empresa_nome: str
    status: str = "executando"  # executando | concluida | erro
    erro: str | None = None
    iniciada_em: datetime = Field(default_factory=datetime.now)
    finalizada_em: datetime | None = None
    parametros: dict[str, Any] = Field(default_factory=dict)
    buscas: list[dict[str, Any]] = Field(default_factory=list)
    candidatos: dict[str, CandidatoProspeccao] = Field(default_factory=dict)
    passos: list[dict[str, Any]] = Field(default_factory=list)
    ranking: list[ItemRanking] = Field(default_factory=list)
    resumo: str = ""
    uso_llm: UsoLLM = Field(default_factory=UsoLLM)
    log: list[EventoLog] = Field(default_factory=list)

    def duracao_s(self) -> float | None:
        if not self.finalizada_em:
            return None
        return (self.finalizada_em - self.iniciada_em).total_seconds()
