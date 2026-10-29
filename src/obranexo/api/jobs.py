"""Execução de tarefas longas (análises, prospecções) em segundo plano, com eventos acompanháveis via SSE.

Cada job e cada evento ficam também no SQLite data/obranexo.db: depois de um reinício do servidor (deploy, contêiner
reiniciado), /api/jobs/{id} continua respondendo e o que estava em andamento é retomado (análises, que só releem
o caso congelado) ou marcado como interrompido (prospecção e chat, que gastariam cota de IA sem ninguém pedir).
"""

from __future__ import annotations

import contextvars
import json
import sqlite3
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from obranexo import contas
from obranexo.config import config
from obranexo.models import Empresa, EventoLog

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tarefa")
# Mensagens do assistente e buscas no PNCP não esperam na fila das análises longas
_EXECUTOR_CHAT = ThreadPoolExecutor(max_workers=4, thread_name_prefix="chat")

INTERROMPIDO = "interrompido pelo reinício do servidor; inicie de novo"

_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  tipo TEXT NOT NULL,
  alvo TEXT NOT NULL,
  empresa_id TEXT,
  status TEXT NOT NULL,
  resultado_id TEXT,
  erro TEXT,
  dados TEXT,
  parametros TEXT,
  iniciado_em TEXT NOT NULL,
  finalizado_em TEXT
);
CREATE TABLE IF NOT EXISTS job_eventos (
  job_id TEXT NOT NULL REFERENCES jobs(id),
  ordem INTEGER NOT NULL,
  evento TEXT NOT NULL,
  PRIMARY KEY (job_id, ordem)
);
"""

_lock_db = threading.Lock()
_preparados: set[str] = set()


def _conectar() -> sqlite3.Connection:
    caminho = config.caminho_db
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho, timeout=5)
    if str(caminho) not in _preparados:
        con.executescript(_DDL)
        _preparados.add(str(caminho))
    return con


@dataclass
class Job:
    id: str
    tipo: str  # analise | prospeccao | chat | busca
    alvo: str
    status: str = "executando"  # executando | concluida | erro
    eventos: list[dict[str, Any]] = field(default_factory=list)
    resultado_id: str | None = None
    erro: str | None = None
    iniciado_em: datetime = field(default_factory=datetime.now)
    finalizado_em: datetime | None = None
    dados: dict[str, Any] | None = None  # resultado inline (ex.: a resposta do assistente)
    empresa_id: str | None = field(default_factory=contas.empresa_ativa)  # dona do job: só ela o acompanha
    parametros: dict[str, Any] = field(default_factory=dict)  # o necessário para retomar depois de um reinício

    def registrar(self, ev: EventoLog) -> None:
        evento = ev.model_dump(mode="json")
        # Um lock só para a ordem e a gravação: lotes em paralelo de uma análise emitem eventos ao mesmo tempo
        with _lock_db:
            self.eventos.append(evento)
            try:
                with _conectar() as con:
                    con.execute("INSERT OR REPLACE INTO job_eventos (job_id, ordem, evento) VALUES (?, ?, ?)",
                                (self.id, len(self.eventos) - 1, json.dumps(evento, ensure_ascii=False)))
            except sqlite3.Error:
                pass  # o evento continua em memória; gravar é o que permite retomar, não o que faz a tarefa andar

    def gravar(self) -> None:
        with _lock_db, _conectar() as con:
            con.execute(
                "INSERT OR REPLACE INTO jobs (id, tipo, alvo, empresa_id, status, resultado_id, erro, dados, parametros, iniciado_em, finalizado_em)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (self.id, self.tipo, self.alvo, self.empresa_id, self.status, self.resultado_id, self.erro,
                 json.dumps(self.dados, ensure_ascii=False, default=str) if self.dados is not None else None,
                 json.dumps(self.parametros, ensure_ascii=False), self.iniciado_em.isoformat(),
                 self.finalizado_em.isoformat() if self.finalizado_em else None),
            )

    def resumo(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tipo": self.tipo,
            "caso": self.alvo,
            "status": self.status,
            "resultado_id": self.resultado_id,
            "analise_id": self.resultado_id if self.tipo == "analise" else None,
            "prospeccao_id": self.resultado_id if self.tipo == "prospeccao" else None,
            "erro": self.erro,
            "dados": self.dados,
            "eventos": len(self.eventos),
            "iniciado_em": self.iniciado_em.isoformat(),
            "finalizado_em": self.finalizado_em.isoformat() if self.finalizado_em else None,
        }


def _job_do_banco(linha: tuple, eventos: list[dict[str, Any]]) -> Job:
    id_, tipo, alvo, empresa_id, status, resultado_id, erro, dados, parametros, iniciado_em, finalizado_em = linha
    return Job(id=id_, tipo=tipo, alvo=alvo, status=status, eventos=eventos, resultado_id=resultado_id, erro=erro,
               iniciado_em=datetime.fromisoformat(iniciado_em),
               finalizado_em=datetime.fromisoformat(finalizado_em) if finalizado_em else None,
               dados=json.loads(dados) if dados else None, empresa_id=empresa_id, parametros=json.loads(parametros or "{}"))


def _ler(job_id: str | None = None, status: str | None = None) -> list[Job]:
    condicao, valores = ("id = ?", (job_id,)) if job_id else ("status = ?", (status,))
    with _conectar() as con:
        linhas = con.execute(f"SELECT id, tipo, alvo, empresa_id, status, resultado_id, erro, dados, parametros, iniciado_em, finalizado_em"
                             f" FROM jobs WHERE {condicao} ORDER BY iniciado_em", valores).fetchall()
        saida = []
        for linha in linhas:
            eventos = [json.loads(e) for (e,) in con.execute("SELECT evento FROM job_eventos WHERE job_id = ? ORDER BY ordem", (linha[0],))]
            saida.append(_job_do_banco(linha, eventos))
    return saida


# Uma tarefa recebe o Job (para emitir eventos) e devolve (id do resultado, status, erro)
Tarefa = Callable[[Job], tuple[str | None, str, str | None]]


class GerenciadorJobs:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def obter(self, job_id: str) -> Job | None:
        """O job, se for da empresa ativa. Depois de um reinício, vem do banco."""
        job = self._jobs.get(job_id)
        if job is None:
            achados = _ler(job_id=job_id)
            job = achados[0] if achados else None
        return job if job is not None and job.empresa_id == contas.empresa_ativa() else None

    def iniciar_tarefa(self, tipo: str, alvo: str, tarefa: Tarefa, parametros: dict[str, Any] | None = None) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], tipo=tipo, alvo=alvo, parametros=parametros or {})
        self._enfileirar(job, tarefa)
        return job

    def _enfileirar(self, job: Job, tarefa: Tarefa) -> None:
        with self._lock:
            self._jobs[job.id] = job
        job.gravar()
        # A thread herda o contexto da requisição: a empresa ativa (onde a análise é gravada) e o escopo da trilha
        contexto = contextvars.copy_context()
        (_EXECUTOR_CHAT if job.tipo in ("chat", "busca") else _EXECUTOR).submit(contexto.run, self._executar, job, tarefa)

    def iniciar(self, caso: str, diretorio: Path, empresa: Empresa) -> Job:
        """Análise de um caso congelado."""
        return self.iniciar_tarefa("analise", caso, tarefa_de_analise(diretorio, empresa), parametros={"caso": caso})

    def retomar(self, preparar: Callable[[Job], Tarefa | None]) -> list[Job]:
        """Na subida do servidor: cada job que estava em andamento é retomado, com o mesmo id, se `preparar` devolver
        a tarefa de novo (rodando na empresa do job); senão, fica marcado como interrompido."""
        retomados = []
        for job in _ler(status="executando"):
            if job.id in self._jobs:  # ainda rodando neste processo
                continue
            with contas.na_empresa(job.empresa_id):
                try:
                    tarefa = preparar(job)
                except Exception:  # caso apagado, catálogo ilegível: melhor interromper que derrubar a subida
                    tarefa = None
                if tarefa is None:
                    job.status, job.erro, job.finalizado_em = "erro", INTERROMPIDO, datetime.now()
                    job.registrar(EventoLog(no="erro", mensagem=f"Tarefa {INTERROMPIDO}."))
                    job.gravar()
                    continue
                job.registrar(EventoLog(no="retomar", mensagem="O servidor reiniciou: a tarefa recomeçou do início."))
                self._enfileirar(job, tarefa)
                retomados.append(job)
        return retomados

    @staticmethod
    def _executar(job: Job, tarefa: Tarefa) -> None:
        try:
            job.resultado_id, job.status, job.erro = tarefa(job)
        except Exception as exc:  # erro fora do fluxo (ex.: caso corrompido)
            job.status = "erro"
            job.erro = f"{type(exc).__name__}: {exc}"
        finally:
            job.finalizado_em = datetime.now()
            try:
                job.gravar()
            except sqlite3.Error:
                pass


def tarefa_de_analise(diretorio: Path, empresa: Empresa) -> Tarefa:
    """A análise de um caso congelado; também é o que se retoma depois de um reinício."""

    def tarefa(job: Job):
        from obranexo.agents.pipeline import executar_caso

        analise = executar_caso(diretorio, empresa, on_evento=job.registrar)
        return analise.id, ("concluida" if analise.status == "concluida" else "erro"), analise.erro

    return tarefa


jobs = GerenciadorJobs()
