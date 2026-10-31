"""Trilha de chamadas de modelo: cada chamada a um provedor de LLM vira uma linha consultável.

Responde "o que aconteceu nesta análise?" depois do fato: qual agente chamou, qual modelo respondeu
(pedido × usado, para ver quando o reserva entrou), tokens de entrada, saída e raciocínio lidos da
própria resposta da API, custo pela tabela oficial, latência, se veio do cache e qual foi o erro.
Fica no banco da aplicação (db.py: SQLite em data/obranexo.db ou PostgreSQL) e é consultada pela API
(/api/analises/{id}/chamadas e /api/metricas/llm).

Quem chamou é informado por escopo: cada agente abre `with escopo(agente="investigador")` ao começar e
toda chamada de modelo dentro do bloco é atribuída a ele. O escopo é um contextvar, por isso vale também
nos lotes em paralelo do Analista Técnico (cada thread recebe uma cópia do contexto).
"""

from __future__ import annotations

import contextvars
import statistics
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Row, text

from obranexo import db
from obranexo.observability import logs

RESUMO_MAX_CHARS = 600


@dataclass(frozen=True)
class Escopo:
    """Quem está chamando o modelo e em nome de que trabalho."""

    agente: str = "sistema"
    versao_prompt: str | None = None
    origem_tipo: str | None = None  # analise | prospeccao | chat | importacao | teste
    origem_id: str | None = None


_ESCOPO_PADRAO = Escopo()  # imutável (frozen): seguro como valor padrão do contextvar
_escopo: contextvars.ContextVar[Escopo] = contextvars.ContextVar("obranexo_escopo", default=_ESCOPO_PADRAO)


@contextmanager
def escopo(**campos: Any) -> Iterator[Escopo]:
    """Abre um escopo (agente, origem) que vale para as chamadas de modelo feitas dentro do bloco.
    Campos omitidos herdam do escopo externo: o pipeline abre a origem e cada agente só informa o nome."""
    novo = replace(_escopo.get(), **{k: v for k, v in campos.items() if v is not None})
    token = _escopo.set(novo)
    try:
        yield novo
    finally:
        _escopo.reset(token)


def escopo_atual() -> Escopo:
    return _escopo.get()


@dataclass
class ChamadaLLM:
    id: str
    quando: str
    origem_tipo: str | None
    origem_id: str | None
    agente: str
    versao_prompt: str | None
    operacao: str  # extrair | texto | conversa
    provedor: str
    modelo_pedido: str
    modelo_usado: str | None = None
    tokens_entrada: int = 0
    tokens_saida: int = 0
    tokens_raciocinio: int = 0
    tokens_cache_leitura: int = 0
    tokens_cache_escrita: int = 0
    custo_usd: float = 0.0
    latencia_ms: int = 0
    cache_hit: bool = False
    reserva: bool = False  # o modelo que respondeu não foi o pedido
    status: str = "ok"  # ok | erro
    erro: str | None = None
    entrada_resumo: str | None = None  # começo do prompt (ou da última mensagem da conversa)
    saida_resumo: str | None = None  # começo da resposta

    @staticmethod
    def nova(operacao: str, provedor: str, modelo: str, entrada: str = "") -> ChamadaLLM:
        esc = escopo_atual()
        return ChamadaLLM(
            id=uuid.uuid4().hex[:12],
            quando=datetime.now().isoformat(timespec="milliseconds"),
            origem_tipo=esc.origem_tipo,
            origem_id=esc.origem_id,
            agente=esc.agente,
            versao_prompt=esc.versao_prompt,
            operacao=operacao,
            provedor=provedor,
            modelo_pedido=modelo,
            entrada_resumo=resumir(entrada),
        )


def resumir(texto: Any) -> str | None:
    t = str(texto or "").strip()
    return (t[:RESUMO_MAX_CHARS] + "…") if len(t) > RESUMO_MAX_CHARS else (t or None)



class Trilha:
    """Grava e consulta a tabela chamadas_llm (db.py). Uma conexão curta por operação: simples e seguro entre threads."""

    def __init__(self, caminho: Path | None = None):
        self._caminho = caminho  # SQLite explícito (testes); sem ele, o banco da aplicação
        self._lock = threading.Lock()

    # ------------------------------------------------------------ escrita

    def gravar(self, chamada: ChamadaLLM) -> None:
        dados = asdict(chamada)
        dados["custo_usd"] = round(dados["custo_usd"], 6)
        with self._lock, db.escrever(self._caminho) as con:
            db.inserir_ou_substituir(con, db.chamadas_llm, {k: (int(v) if isinstance(v, bool) else v) for k, v in dados.items()})
        logs.registrar("chamada_llm", **{k: v for k, v in dados.items() if k not in {"entrada_resumo", "saida_resumo"}})

    # ------------------------------------------------------------ leitura

    def listar(self, origem_id: str) -> list[dict[str, Any]]:
        with db.ler(self._caminho) as con:
            linhas = con.execute(text("SELECT * FROM chamadas_llm WHERE origem_id = :origem_id ORDER BY quando"), {"origem_id": origem_id}).fetchall()
        return [_dict(linha) for linha in linhas]

    def resumo(self, origem_id: str | None = None) -> dict[str, Any]:
        """Agregados para a tela de métricas: totais, latência (média e p95), taxas e quebras por agente e por modelo."""
        filtro, params = ("WHERE origem_id = :origem_id", {"origem_id": origem_id}) if origem_id else ("", {})
        with db.ler(self._caminho) as con:
            linhas = [_dict(linha) for linha in con.execute(text(f"SELECT * FROM chamadas_llm {filtro} ORDER BY quando"), params).fetchall()]
        return agregar(linhas)


def _dict(linha: Row) -> dict[str, Any]:
    d = dict(linha._mapping)
    d["cache_hit"] = bool(d["cache_hit"])
    d["reserva"] = bool(d["reserva"])
    return d


def agregar(chamadas: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(chamadas)
    reais = [c for c in chamadas if not c["cache_hit"]]  # latência só faz sentido para o que foi ao provedor
    latencias = sorted(c["latencia_ms"] for c in reais) or [0]

    def _grupo(chave: str) -> list[dict[str, Any]]:
        grupos: dict[str, list[dict[str, Any]]] = {}
        for c in chamadas:
            grupos.setdefault(c.get(chave) or "—", []).append(c)
        saida = []
        for nome, grupo in grupos.items():
            sem_cache = [c for c in grupo if not c["cache_hit"]]
            saida.append(
                {
                    chave: nome,
                    "chamadas": len(grupo),
                    "custo_usd": round(sum(c["custo_usd"] for c in grupo), 6),
                    "tokens_entrada": sum(c["tokens_entrada"] for c in grupo),
                    "tokens_saida": sum(c["tokens_saida"] for c in grupo),
                    "tokens_raciocinio": sum(c["tokens_raciocinio"] for c in grupo),
                    "latencia_media_ms": int(statistics.mean(c["latencia_ms"] for c in sem_cache)) if sem_cache else 0,
                    "cache_hits": len(grupo) - len(sem_cache),
                    "reservas": sum(1 for c in grupo if c["reserva"]),
                    "erros": sum(1 for c in grupo if c["status"] == "erro"),
                }
            )
        saida.sort(key=lambda g: g["custo_usd"], reverse=True)
        return saida

    return {
        "chamadas": n,
        "chamadas_api": len(reais),
        "custo_usd": round(sum(c["custo_usd"] for c in chamadas), 6),
        "tokens": {
            "entrada": sum(c["tokens_entrada"] for c in chamadas),
            "saida": sum(c["tokens_saida"] for c in chamadas),
            "raciocinio": sum(c["tokens_raciocinio"] for c in chamadas),
            "cache_leitura": sum(c["tokens_cache_leitura"] for c in chamadas),
        },
        "latencia_ms": {
            "media": int(statistics.mean(latencias)) if reais else 0,
            "p95": int(latencias[max(0, int(round(0.95 * len(latencias))) - 1)]) if reais else 0,
            "maxima": int(latencias[-1]) if reais else 0,
        },
        "taxa_cache": round((n - len(reais)) / n, 3) if n else 0.0,
        "taxa_reserva": round(sum(1 for c in chamadas if c["reserva"]) / n, 3) if n else 0.0,
        "taxa_erro": round(sum(1 for c in chamadas if c["status"] == "erro") / n, 3) if n else 0.0,
        "por_agente": _grupo("agente"),
        "por_modelo": _grupo("modelo_usado"),
    }


trilha = Trilha()
