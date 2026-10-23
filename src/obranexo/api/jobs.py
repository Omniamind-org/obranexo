"""Execução das análises em segundo plano, com eventos acompanháveis pela API (SSE)."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from obranexo.models import Empresa

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="analise")


@dataclass
class Job:
    id: str
    caso: str
    status: str = "executando"  # executando | concluida | erro
    eventos: list[dict[str, Any]] = field(default_factory=list)
    analise_id: str | None = None
    erro: str | None = None
    iniciado_em: datetime = field(default_factory=datetime.now)
    finalizado_em: datetime | None = None

    def resumo(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "caso": self.caso,
            "status": self.status,
            "analise_id": self.analise_id,
            "erro": self.erro,
            "eventos": len(self.eventos),
            "iniciado_em": self.iniciado_em.isoformat(),
            "finalizado_em": self.finalizado_em.isoformat() if self.finalizado_em else None,
        }


class GerenciadorJobs:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def obter(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def iniciar(self, caso: str, diretorio: Path, empresa: Empresa) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], caso=caso)
        with self._lock:
            self._jobs[job.id] = job
        _EXECUTOR.submit(self._executar, job, diretorio, empresa)
        return job

    @staticmethod
    def _executar(job: Job, diretorio: Path, empresa: Empresa) -> None:
        from obranexo.agents.pipeline import executar_caso

        try:
            analise = executar_caso(diretorio, empresa, on_evento=lambda ev: job.eventos.append(ev.model_dump(mode="json")))
            job.analise_id = analise.id
            job.status = "concluida" if analise.status == "concluida" else "erro"
            job.erro = analise.erro
        except Exception as exc:  # erro fora do pipeline (ex.: caso corrompido)
            job.status = "erro"
            job.erro = f"{type(exc).__name__}: {exc}"
        finally:
            job.finalizado_em = datetime.now()


jobs = GerenciadorJobs()
