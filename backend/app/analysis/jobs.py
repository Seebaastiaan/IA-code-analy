"""
Jobs de análisis (en memoria del proceso). El paso 1 (clonar) es REAL: descarga el repo con git, usando el
token de GitHub del usuario si lo tiene. Después corren Ruff, Bandit y Radon sobre el clon
(app.analysis.pipeline); el entorno, las dependencias, pip-audit, pytest y coverage se simulan hasta tener
sandbox. La terminal del usuario avanza por WebSocket con cada paso y al final se guarda el reporte.
"""

import asyncio
import logging
import random
import secrets
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from cryptography.fernet import Fernet

from app.analyses.analyzers import AnalyzerError
from app.analyses.store import AnalysisStore
from app.analyses.views import report_scores
from app.analyses.workspace import Workspace
from app.analysis import fake, languages, pipeline
from app.analysis.clone import CloneError, Cloner, clone_dir
from app.config import Settings
from app.db import session
from app.github.store import GithubAccountStore

log = logging.getLogger(__name__)
# "Indexando para el asistente" en fake.JOB_STEPS
INDEX_STEP = 10


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class Job:
    id: str
    user_id: str
    team_id: str
    repo_id: str
    url: str
    name: str
    branch: str
    seed: int
    cat: dict
    # Inicio del análisis (time.monotonic) para la duración que muestra el reporte
    started: float = field(default_factory=time.monotonic)
    step: int = 0
    total: int = len(fake.JOB_STEPS)
    status: str = "running"
    logs: list[str] = field(default_factory=list)
    error: dict | None = None
    commit: str | None = None
    report_id: str | None = None
    # Lenguajes del repo (al clonar); el reporte los muestra
    repo_languages: list[languages.Language] = field(default_factory=list)
    result: pipeline.PipelineResult | None = None
    listeners: set[asyncio.Queue] = field(default_factory=set)
    task: asyncio.Task | None = None

    def public(self) -> dict:
        return {
            "id": self.id, "url": self.url, "name": self.name, "branch": self.branch, "step": self.step, "total": self.total,
            "status": self.status, "logs": list(self.logs), "error": self.error, "repo_id": self.repo_id, "report_id": self.report_id,
        }


class JobManager:
    def __init__(self, cloner: Cloner | None = None) -> None:
        self._jobs: dict[str, Job] = {}
        self.cloner = cloner or Cloner()

    # ─── Consulta ───

    def get(self, conn: sqlite3.Connection, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def running_for_repo(self, conn: sqlite3.Connection, repo_id: str) -> Job | None:
        return next((j for j in self._jobs.values() if j.repo_id == repo_id and j.status == "running"), None)

    # ─── Eventos ───

    def _emit(self, job: Job, msg: dict) -> None:
        if msg["type"] == "log":
            job.logs.append(msg["line"])
        for q in job.listeners:
            q.put_nowait(msg)

    def subscribe(self, job: Job) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        q.put_nowait({"type": "snapshot", "job": job.public()})
        job.listeners.add(q)
        return q

    def unsubscribe(self, job: Job, q: asyncio.Queue) -> None:
        job.listeners.discard(q)

    # ─── Ciclo de vida ───

    def start(self, settings: Settings, user_id: str, team_id: str, repo_id: str, url: str, name: str, branch: str, prev_cat: dict | None) -> Job:
        seed = random.randrange(2**31)
        job = Job(
            id=f"job-{secrets.token_hex(8)}", user_id=user_id, team_id=team_id, repo_id=repo_id, url=url, name=name, branch=branch,
            seed=seed, cat=fake.next_categories(prev_cat, random.Random(seed)), logs=[f"$ ia-voy analyze {url} --branch {branch}"],
        )
        self._jobs[job.id] = job
        job.task = asyncio.create_task(self._run(settings, job))
        return job

    def _start_step(self, job: Job) -> None:
        name, command = fake.JOB_STEPS[job.step]
        command = command.format(branch=job.branch, url=job.url)
        self._emit(job, {"type": "step", "index": job.step, "total": job.total, "name": name, "command": command})
        self._emit(job, {"type": "log", "line": f"[{job.step + 1:02d}/{job.total}] {name} → {command}"})

    def _finish_step(self, job: Job, summary: str | None) -> None:
        if summary:
            self._emit(job, {"type": "log", "line": summary})
        self._emit(job, {"type": "log", "line": "  ✓ ok"})
        job.step += 1
        self._emit(job, {"type": "step_done", "index": job.step - 1})

    def _fail(self, settings: Settings, job: Job, err: CloneError) -> None:
        job.status = "error"
        job.error = {"title": err.title, "detail": err.detail, "hint": err.hint}
        self._emit(job, {"type": "log", "line": f"  ERROR: {err.detail}"})
        self._emit(job, {"type": "error", "step": job.step, **job.error})
        _set_repo(settings, job.repo_id, "error", err.title)

    async def _clone(self, settings: Settings, job: Job) -> bool:
        """Paso 1 real. Devuelve False si falló (el job queda en error)."""
        attempt = secrets.token_hex(4)
        token = _github_token(settings, job.user_id)
        try:
            result = await asyncio.to_thread(self.cloner.clone, settings, job.repo_id, job.url, job.branch, token, attempt)
        except CloneError as err:
            self._fail(settings, job, err)
            return False
        await asyncio.to_thread(self.cloner.promote, settings, job.repo_id, attempt)
        job.commit = result.commit
        # IA voy analiza solo Python: sin Python no hay nada que analizar; con poco, se avisa.
        # El conteo ignora dependencias y entornos subidos al repo (node_modules, venv…).
        job.repo_languages = await asyncio.to_thread(languages.detect, clone_dir(settings, job.repo_id))
        py = languages.python_files(job.repo_languages)
        with session(settings.database_path) as conn:
            conn.execute("UPDATE repos SET files = ? WHERE id = ?", (py, job.repo_id))
        found = f"  lenguajes: {languages.summary(job.repo_languages)}"
        if py == 0:
            self._emit(job, {"type": "log", "line": found})
            self._fail(settings, job, CloneError(
                "El repositorio no tiene código Python",
                f"IA voy analiza proyectos Python y en este repositorio hay: {languages.summary(job.repo_languages)}.",
                "Elige un repositorio con archivos .py (los notebooks .ipynb todavía no se analizan).",
            ))
            return False
        code = sum(lang.files for lang in job.repo_languages if lang.name not in languages.MARKUP)
        if py * 2 < code:
            found += f"\n  aviso: solo {py} de {code} archivos de código son Python; el resto no se analiza"
        self._finish_step(job, f"  commit {result.commit} · {py} archivos .py · {result.seconds} s\n{found}")
        return True

    async def _analyze(self, settings: Settings, job: Job) -> bool:
        """
        Pasos 2-7. Ruff, Bandit y Radon corren en un hilo mientras la terminal avanza; el entorno, las
        dependencias, pip-audit, pytest y coverage se simulan. Deja `job.result` listo.
        """
        static_task = asyncio.create_task(asyncio.to_thread(pipeline.analyze_static, settings, job.repo_id))
        try:
            while job.step <= pipeline.COVERAGE_STEP:
                self._start_step(job)
                if job.step >= pipeline.BANDIT_STEP and job.result is None:
                    static = await static_task
                    job.result = await asyncio.to_thread(pipeline.build, settings, job.repo_id, static, job.branch, job.commit, job.seed, job.cat)
                await asyncio.sleep(settings.job_step_seconds)
                self._finish_step(job, pipeline.step_summary(job.step, job.result))
        except AnalyzerError as exc:
            self._fail(settings, job, CloneError("Los analizadores fallaron", str(exc), "Vuelve a intentarlo; si se repite, revisa el log del backend."))
            return False
        return True

    async def _run(self, settings: Settings, job: Job) -> None:
        try:
            self._start_step(job)
            if not await self._clone(settings, job):
                return
            if not await self._analyze(settings, job):
                return
            while job.step < job.total:
                self._start_step(job)
                await asyncio.sleep(settings.job_step_seconds)
                summary = "  omitido: el asistente IA aún no está habilitado" if job.step == INDEX_STEP else pipeline.step_summary(job.step, job.result)
                self._finish_step(job, summary)
            num, score = _save_report(settings, job)
            job.status = "done"
            self._emit(job, {"type": "log", "line": f"Análisis #{num} completado."})
            self._emit(job, {"type": "done", "repo_id": job.repo_id, "report_id": job.report_id, "num": num, "score": score})
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            # Nunca dejar un job colgado en "running": el usuario ve el error y puede volver a analizar
            log.exception("Fallo inesperado en el job %s", job.id)
            self._fail(settings, job, CloneError("Error inesperado durante el análisis", f"{type(exc).__name__}: {exc}", "Vuelve a intentarlo; si se repite, revisa la terminal del backend."))


def _github_token(settings: Settings, user_id: str) -> str | None:
    with session(settings.database_path) as conn:
        account = GithubAccountStore(conn, Fernet(settings.token_encryption_key)).get(user_id)
    return account.token if account else None


def _set_repo(settings: Settings, repo_id: str, status: str, error: str | None) -> None:
    with session(settings.database_path) as conn:
        conn.execute("UPDATE repos SET status = ?, error = ? WHERE id = ?", (status, error, repo_id))


def _save_report(settings: Settings, job: Job) -> tuple[int, float]:
    """Guarda el reporte con sus hallazgos (app.analyses) y devuelve (número, score global)."""
    with session(settings.database_path) as conn:
        store = AnalysisStore(conn)
        job.result.report.duration_s = round(time.monotonic() - job.started)
        job.result.report.languages = [{"name": lang.name, "files": lang.files} for lang in job.repo_languages]
        job.report_id, num = store.save_report(job.repo_id, job.result.report, Workspace(settings, job.repo_id))
        conn.execute("UPDATE repos SET status = 'listo', error = NULL, branch = ? WHERE id = ?", (job.branch, job.repo_id))
        score = report_scores(store, store.report(job.report_id), store.config(job.repo_id)).global_
    return num, score


jobs = JobManager()
