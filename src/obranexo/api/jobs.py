"""Execução de tarefas longas (análises, prospecções) em segundo plano, com eventos acompanháveis via SSE."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from obranexo.models import Empresa, EventoLog

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="tarefa")


@dataclass
class Job:
    id: str
    tipo: str  # analise | prospeccao
    alvo: str
    status: str = "executando"  # executando | concluida | erro
    eventos: list[dict[str, Any]] = field(default_factory=list)
    resultado_id: str | None = None
    erro: str | None = None
    iniciado_em: datetime = field(default_factory=datetime.now)
    finalizado_em: datetime | None = None

    def registrar(self, ev: EventoLog) -> None:
        self.eventos.append(ev.model_dump(mode="json"))

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
            "eventos": len(self.eventos),
            "iniciado_em": self.iniciado_em.isoformat(),
            "finalizado_em": self.finalizado_em.isoformat() if self.finalizado_em else None,
        }


# Uma tarefa recebe o Job (para emitir eventos) e devolve (id do resultado, status, erro)
Tarefa = Callable[[Job], tuple[str | None, str, str | None]]


class GerenciadorJobs:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def obter(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def iniciar_tarefa(self, tipo: str, alvo: str, tarefa: Tarefa) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], tipo=tipo, alvo=alvo)
        with self._lock:
            self._jobs[job.id] = job
        _EXECUTOR.submit(self._executar, job, tarefa)
        return job

    def iniciar(self, caso: str, diretorio: Path, empresa: Empresa) -> Job:
        """Análise de um caso congelado."""

        def tarefa(job: Job):
            from obranexo.agents.pipeline import executar_caso

            analise = executar_caso(diretorio, empresa, on_evento=job.registrar)
            return analise.id, ("concluida" if analise.status == "concluida" else "erro"), analise.erro

        return self.iniciar_tarefa("analise", caso, tarefa)

    @staticmethod
    def _executar(job: Job, tarefa: Tarefa) -> None:
        try:
            job.resultado_id, job.status, job.erro = tarefa(job)
        except Exception as exc:  # erro fora do fluxo (ex.: caso corrompido)
            job.status = "erro"
            job.erro = f"{type(exc).__name__}: {exc}"
        finally:
            job.finalizado_em = datetime.now()


jobs = GerenciadorJobs()
