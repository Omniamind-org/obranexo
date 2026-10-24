"""O grafo da análise como dado: cada nó declara o que lê, o que escreve e quando roda.

A orquestração do ObraNexo é uma sequência explícita em Python (sem framework): os nós são funções que
leem e escrevem no mesmo estado compartilhado (agents/contexto.py). Este módulo dá forma a essa
sequência — `Grafo.executar` é quem roda a análise em pipeline.py — e a torna consultável: a API expõe
(/api/conteudo/grafo), a tela "Sobre" mostra e docs/FLUXO_DO_AGENTE.md é gerado daqui. É a resposta
para "quais são as etapas, o que cada uma recebe e entrega, onde fica o estado".
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from obranexo.agents.contexto import Contexto


@dataclass(frozen=True)
class No:
    nome: str  # id da etapa; é o `no` dos eventos da trilha (Contexto.evento)
    titulo: str
    descricao: str
    executar: Callable[[Contexto], None]
    arquivo: str
    agente: str | None = None  # nome do agente na trilha de chamadas (observability/trilha.py); None = só regras
    modelo: str | None = None  # "agente" | "extracao" quando usa um modelo de linguagem
    condicao: str | None = None  # em palavras, quando a etapa roda; None = sempre
    quando: Callable[[Contexto], bool] | None = None  # a mesma condição, em código
    le: tuple[str, ...] = ()  # campos do estado que a etapa consome
    escreve: tuple[str, ...] = ()  # campos do estado que a etapa produz ou altera

    @property
    def usa_llm(self) -> bool:
        return self.modelo is not None

    def como_dict(self, ordem: int) -> dict[str, Any]:
        return {
            "ordem": ordem,
            "nome": self.nome,
            "titulo": self.titulo,
            "agente": self.agente,
            "usa_llm": self.usa_llm,
            "modelo": self.modelo,
            "condicao": self.condicao,
            "le": list(self.le),
            "escreve": list(self.escreve),
            "descricao": self.descricao,
            "arquivo": self.arquivo,
        }


@dataclass(frozen=True)
class Grafo:
    nos: tuple[No, ...]
    estado: dict[str, Any]  # descrição do estado compartilhado: {"descricao": ..., "campos": [...]}

    def __post_init__(self) -> None:
        nomes = [n.nome for n in self.nos]
        if len(nomes) != len(set(nomes)):
            raise ValueError(f"nós com nome repetido: {nomes}")

    def executar(self, ctx: Contexto) -> None:
        """Roda os nós em ordem. Um nó condicional que não se aplica é pulado e isso fica na trilha da análise."""
        for no in self.nos:
            if no.quando is not None and not no.quando(ctx):
                ctx.evento(no.nome, f"Etapa não se aplica ({no.condicao})")
                continue
            no.executar(ctx)

    def descrever(self) -> dict[str, Any]:
        return {"nos": [no.como_dict(i) for i, no in enumerate(self.nos, start=1)], "estado": self.estado, "mermaid": self.mermaid()}

    def mermaid(self) -> str:
        """Fluxograma Mermaid: nós de LLM em verde-água, nós condicionais tracejados, aresta rotulada pela condição."""
        linhas = ["flowchart TD"]
        for no in self.nos:
            rotulo = f"{no.titulo}<br/><small>{no.agente or 'regras'}{' · LLM' if no.usa_llm else ''}</small>"
            linhas.append(f'  {no.nome}["{rotulo}"]')
        for a, b in zip(self.nos, self.nos[1:], strict=False):
            linhas.append(f"  {a.nome} -->{f'|{b.condicao}|' if b.condicao else ''} {b.nome}")
        llm = [n.nome for n in self.nos if n.usa_llm]
        cond = [n.nome for n in self.nos if n.condicao]
        linhas.append("  classDef llm fill:#e2f4f2,stroke:#00ab9f,color:#10222f")
        linhas.append("  classDef cond stroke-dasharray:5 4")
        if llm:
            linhas.append(f"  class {','.join(llm)} llm")
        if cond:
            linhas.append(f"  class {','.join(cond)} cond")
        return "\n".join(linhas)

    def markdown(self) -> str:
        """Tabela de inputs, lógica e outputs por etapa, para a documentação do fluxo."""
        linhas = ["| # | Etapa | Quem | Lê (inputs) | Faz (lógica) | Escreve (outputs) | Quando |", "|---|---|---|---|---|---|---|"]
        for i, no in enumerate(self.nos, start=1):
            quem = (no.agente or "regras") + (f" · LLM ({no.modelo})" if no.usa_llm else "")
            linhas.append(
                f"| {i} | **{no.titulo}** `{no.nome}` | {quem} | {', '.join(f'`{c}`' for c in no.le)} | {no.descricao} "
                f"| {', '.join(f'`{c}`' for c in no.escreve)} | {no.condicao or 'sempre'} |"
            )
        return "\n".join(linhas)
