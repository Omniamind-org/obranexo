"""Configuração central: caminhos, provedor de LLM, modelos e limites lidos do .env / ambiente."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / ".env")

PROVEDORES = ("gemini", "groq", "anthropic")

# Modelos padrão por provedor (cada um pode ser trocado no .env: OBRANEXO_<PROVEDOR>_MODEL_AGENTE etc.).
# - Gemini: família 3.x para contas novas (gemini-2.5-flash já não é oferecido).
# - Groq: gpt-oss tem saída estruturada por json_schema e bom uso de ferramentas; o reserva é Llama 3.3.
#   No nível gratuito o limite de tokens por minuto é baixo, por isso lotes menores de extração.
MODELOS_PADRAO: dict[str, dict] = {
    "gemini": {"agente": "gemini-3.8-flash", "extracao": "gemini-3.5-flash-lite", "reserva": ["gemini-3.5-flash-lite"], "lote": (10, 9000)},
    "groq": {"agente": "openai/gpt-oss-120b", "extracao": "openai/gpt-oss-20b", "reserva": ["llama-3.3-70b-versatile"], "lote": (5, 4500)},
    "anthropic": {"agente": "claude-sonnet-5-5", "extracao": "claude-haiku-5-5", "reserva": [], "lote": (10, 9000)},
}

_VAR_CHAVE = {"gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"), "groq": ("GROQ_API_KEY",), "anthropic": ("ANTHROPIC_API_KEY",)}


def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(os.getenv(nome, padrao))
    except ValueError:
        return padrao


def _env_bool(nome: str, padrao: bool) -> bool:
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "sim", "yes", "on"}


def _chave(provedor: str) -> str | None:
    return next((os.getenv(v) for v in _VAR_CHAVE[provedor] if os.getenv(v)), None)


def _provedor_auto() -> str | None:
    explicito = (os.getenv("OBRANEXO_LLM_PROVIDER") or "").strip().lower()
    if explicito in PROVEDORES:
        return explicito
    if explicito in {"none", "nenhum", "off"}:
        return None
    return next((p for p in PROVEDORES if _chave(p)), None)


@dataclass
class Config:
    raiz: Path = RAIZ
    dir_dados: Path = RAIZ / "data"
    dir_casos: Path = RAIZ / "data" / "casos"
    dir_cache: Path = RAIZ / "data" / "cache"
    dir_llm_cache: Path = RAIZ / "data" / "llm_cache"
    dir_analises: Path = RAIZ / "data" / "analises"
    catalogo_demo: Path = RAIZ / "data" / "catalogo_demo" / "produtos.json"
    dir_web: Path = RAIZ / "web"

    llm_provider: str | None = field(default_factory=_provedor_auto)
    anthropic_api_key: str | None = field(default_factory=lambda: _chave("anthropic"))
    gemini_api_key: str | None = field(default_factory=lambda: _chave("gemini"))
    groq_api_key: str | None = field(default_factory=lambda: _chave("groq"))
    model_agente: str | None = field(default_factory=lambda: os.getenv("OBRANEXO_MODEL_AGENTE") or None)
    model_extracao: str | None = field(default_factory=lambda: os.getenv("OBRANEXO_MODEL_EXTRACAO") or None)
    modelos_reserva: list[str] = field(default_factory=lambda: [m.strip() for m in os.getenv("OBRANEXO_MODELOS_RESERVA", "").split(",") if m.strip()])
    lote_max_itens: int = 10
    lote_max_chars: int = 9000
    max_passos_investigador: int = field(default_factory=lambda: _env_int("OBRANEXO_MAX_PASSOS_INVESTIGADOR", 12))
    orcamento_tokens: int = field(default_factory=lambda: _env_int("OBRANEXO_ORCAMENTO_TOKENS", 120_000))
    offline: bool = field(default_factory=lambda: _env_bool("OBRANEXO_OFFLINE", False))
    llm_cache: bool = field(default_factory=lambda: _env_bool("OBRANEXO_LLM_CACHE", True))
    llm_pausa_s: float = field(default_factory=lambda: float(os.getenv("OBRANEXO_LLM_PAUSA_S", "0")))
    llm_timeout_s: float = field(default_factory=lambda: float(os.getenv("OBRANEXO_LLM_TIMEOUT_S", "45")))
    llm_paralelo: int = field(default_factory=lambda: _env_int("OBRANEXO_LLM_PARALELO", 4))

    # Preço de tabela (US$ por 1M tokens: entrada, saída) para estimar o custo de IA por análise — métrica interna
    # de margem, não a fatura: o nível gratuito custa 0 e lote/cache dão desconto. Fontes e data em
    # research_notes/Modelo de negócio ObraNexo/modelo_receita_custos.md (preços oficiais de out/2026).
    precos_usd: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {
            "claude-opus-5-5": (4.00, 20.00),
            "claude-sonnet-5-5": (2.00, 10.00),
            "claude-haiku-5-5": (0.10, 0.50),
            "gemini-3.8-flash": (0.75, 3.75),  # promoção até 31/12/2026; depois 1,50 / 7,50
            "gemini-3.5-flash-lite": (0.30, 2.50),
            "openai/gpt-oss-120b": (0.15, 0.60),
            "openai/gpt-oss-20b": (0.075, 0.30),
            "llama-3.3-70b-versatile": (0.59, 0.79),  # fontes de 2026 indicam fim do self-serve em 16/08/2026
            "llama-3.1-8b-instant": (0.05, 0.08),
        }
    )
    # Faixas por chamada: acima de `limite` tokens de entrada, o preço muda (Haiku 5.5 custa 5x acima de 100k)
    precos_faixa_usd: dict[str, tuple[int, float, float]] = field(
        default_factory=lambda: {"claude-haiku-5-5": (100_000, 0.50, 2.50)}
    )
    cambio_brl: float = field(default_factory=lambda: float(os.getenv("OBRANEXO_CAMBIO_BRL", "5.0377")))  # PTAX 23/10/2026
    meta_custo_analise_brl: float = field(default_factory=lambda: float(os.getenv("OBRANEXO_META_CUSTO_ANALISE_BRL", "1.0")))  # KPI do BMC

    def __post_init__(self) -> None:
        if self.llm_provider and not self.chave(self.llm_provider):
            self.llm_provider = None
        self._aplicar_modelos(self.llm_provider, sobrescrever=False)

    # ------------------------------------------------------------------ provedores

    def chave(self, provedor: str) -> str | None:
        return {"gemini": self.gemini_api_key, "groq": self.groq_api_key, "anthropic": self.anthropic_api_key}.get(provedor)

    def provedores_configurados(self) -> list[str]:
        return [p for p in PROVEDORES if self.chave(p)]

    def _aplicar_modelos(self, provedor: str | None, sobrescrever: bool) -> None:
        padrao = MODELOS_PADRAO.get(provedor or "", MODELOS_PADRAO["anthropic"])
        pref = f"OBRANEXO_{(provedor or '').upper()}_"
        agente = os.getenv(pref + "MODEL_AGENTE") or padrao["agente"]
        extracao = os.getenv(pref + "MODEL_EXTRACAO") or padrao["extracao"]
        reserva = [m.strip() for m in os.getenv(pref + "MODELOS_RESERVA", "").split(",") if m.strip()] or list(padrao["reserva"])
        if sobrescrever:
            self.model_agente, self.model_extracao, self.modelos_reserva = agente, extracao, reserva
        else:  # na inicialização, as variáveis genéricas (OBRANEXO_MODEL_AGENTE…) ainda valem
            self.model_agente = self.model_agente or agente
            self.model_extracao = self.model_extracao or extracao
            self.modelos_reserva = self.modelos_reserva or reserva
        self.lote_max_itens, self.lote_max_chars = padrao["lote"]

    def usar_provedor(self, provedor: str | None) -> None:
        """Troca o provedor em tempo de execução (ex.: pela interface). Exige a chave no .env."""
        if provedor is not None and provedor not in PROVEDORES:
            raise ValueError(f"provedor desconhecido: {provedor}")
        if provedor is not None and not self.chave(provedor):
            raise ValueError(f"sem chave configurada para {provedor} ({' ou '.join(_VAR_CHAVE[provedor])} no .env)")
        self.llm_provider = provedor
        self._aplicar_modelos(provedor, sobrescrever=True)

    @property
    def llm_disponivel(self) -> bool:
        return self.llm_provider is not None

    def garantir_diretorios(self) -> None:
        for d in (self.dir_cache, self.dir_llm_cache, self.dir_analises):
            d.mkdir(parents=True, exist_ok=True)


config = Config()
