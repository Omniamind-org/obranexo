"""Configuração central: caminhos, provedor de LLM, modelos e limites lidos do .env / ambiente."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / ".env")

# Modelos padrão por provedor. Gemini: a API recomenda a família 3.x para contas novas
# (gemini-2.5-flash já não é oferecido); o flash-lite é o mais barato/estável do nível gratuito.
MODELOS_PADRAO = {
    "gemini": {"agente": "gemini-3.8-flash", "extracao": "gemini-3.5-flash-lite", "reserva": ["gemini-3.5-flash-lite"]},
    "anthropic": {"agente": "claude-sonnet-5-5", "extracao": "claude-haiku-5-5", "reserva": []},
}


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


def _provedor_auto() -> str | None:
    explicito = (os.getenv("OBRANEXO_LLM_PROVIDER") or "").strip().lower()
    if explicito in {"gemini", "anthropic"}:
        return explicito
    if explicito in {"none", "nenhum", "off"}:
        return None
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return "gemini"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


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
    anthropic_api_key: str | None = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY") or None)
    gemini_api_key: str | None = field(default_factory=lambda: os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or None)
    model_agente: str | None = field(default_factory=lambda: os.getenv("OBRANEXO_MODEL_AGENTE") or None)
    model_extracao: str | None = field(default_factory=lambda: os.getenv("OBRANEXO_MODEL_EXTRACAO") or None)
    modelos_reserva: list[str] = field(default_factory=lambda: [m.strip() for m in os.getenv("OBRANEXO_MODELOS_RESERVA", "").split(",") if m.strip()])
    max_passos_investigador: int = field(default_factory=lambda: _env_int("OBRANEXO_MAX_PASSOS_INVESTIGADOR", 12))
    orcamento_tokens: int = field(default_factory=lambda: _env_int("OBRANEXO_ORCAMENTO_TOKENS", 120_000))
    offline: bool = field(default_factory=lambda: _env_bool("OBRANEXO_OFFLINE", False))
    llm_cache: bool = field(default_factory=lambda: _env_bool("OBRANEXO_LLM_CACHE", True))
    llm_pausa_s: float = field(default_factory=lambda: float(os.getenv("OBRANEXO_LLM_PAUSA_S", "0")))
    llm_timeout_s: float = field(default_factory=lambda: float(os.getenv("OBRANEXO_LLM_TIMEOUT_S", "45")))

    # Preço (US$ por 1M tokens: entrada, saída) para estimar custo por análise.
    # Modelos Gemini no nível gratuito custam 0; preencha com a tabela paga quando migrar.
    precos_usd: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {
            "claude-opus-5-5": (4.00, 20.00),
            "claude-sonnet-5-5": (2.00, 10.00),
            "claude-haiku-5-5": (0.10, 0.50),
            "gemini-3.8-flash": (0.0, 0.0),
            "gemini-3.5-flash-lite": (0.0, 0.0),
            "gemini-3.5-flash": (0.0, 0.0),
        }
    )

    def __post_init__(self) -> None:
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            self.llm_provider = None
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            self.llm_provider = None
        padrao = MODELOS_PADRAO.get(self.llm_provider or "", MODELOS_PADRAO["anthropic"])
        self.model_agente = self.model_agente or padrao["agente"]
        self.model_extracao = self.model_extracao or padrao["extracao"]
        if not self.modelos_reserva:
            self.modelos_reserva = list(padrao["reserva"])

    @property
    def llm_disponivel(self) -> bool:
        return self.llm_provider is not None

    def garantir_diretorios(self) -> None:
        for d in (self.dir_cache, self.dir_llm_cache, self.dir_analises):
            d.mkdir(parents=True, exist_ok=True)


config = Config()
