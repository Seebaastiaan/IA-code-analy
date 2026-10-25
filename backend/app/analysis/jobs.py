"""
Jobs de análisis (Sprint 5: hasta pip-audit).

1. Clonar: REAL. Descarga el repo con git, usando el token de GitHub del usuario si lo tiene, y detecta
   sus lenguajes (IA voy solo analiza Python).
2. Crear entorno aislado: REAL. `uv venv` en el sandbox (SANDBOX=wsl|docker) o `python -m venv` en el
   backend (SANDBOX=off).
3. Instalar dependencias: REAL, solo en el sandbox (instalar ejecuta código del repo).
4. Bandit: REAL. Lee el código en el backend mientras el sandbox avanza.
5. pip-audit: REAL, en el sandbox, sobre las dependencias instaladas.

Al terminar se guarda el análisis en `reports` con sus hallazgos de Seguridad (tabla `findings`). pytest,
coverage, Ruff, Radon y el score llegan en el Sprint 6. La terminal del usuario avanza por WebSocket con
cada paso.

Persistencia (tabla `jobs`): el proceso que corre un job guarda su estado con cada evento y renueva un
latido (`heartbeat`). Así:
- GET /api/jobs/{id} y el WebSocket funcionan desde cualquier worker (el que no lo corre lee la tabla).
- Un job "running" sin latido reciente se interrumpió (reinicio del servidor): se muestra como error y se
  puede reintentar (desde el clonado).
- Cancelar desde otro worker marca el job; el que lo corre lo ve en su latido y lo detiene.
"""

import asyncio
import json
import logging
import secrets
import sqlite3
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime

from cryptography.fernet import Fernet

from app.analyses.analyzers import AnalyzerError
from app.analyses.config_file import import_repo_config
from app.analyses.models import FindingInput
from app.analyses.store import AnalysisStore
from app.analyses.workspace import Workspace
from app.analysis import languages, pipeline, sandbox
from app.analysis.clone import CloneError, Cloner, clone_dir
from app.analysis.steps import AUDIT_STEP, CLONE_STEP, JOB_STEPS, VENV_STEP
from app.config import Settings
from app.db import connect, session
from app.github.store import GithubAccountStore

log = logging.getLogger(__name__)
# Cada cuánto el proceso que corre un job renueva su latido y revisa si lo cancelaron desde otro worker
HEARTBEAT_S = 5.0
# Sin latido por más de esto, el job se considera interrumpido
STALE_S = 30.0
# Cada cuánto el WebSocket de un job que corre en otro worker lee su estado
REMOTE_POLL_S = 0.5

INTERRUPTED = {
    "title": "El análisis se interrumpió",
    "detail": "El servidor se reinició mientras corría el análisis.",
    "hint": "Reintenta: el análisis empieza de nuevo desde el clonado.",
}


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
    db_path: str
    # Crear el entorno, instalar dependencias y correr pip-audit en el sandbox (si SANDBOX lo permite);
    # False = el entorno se crea en el backend y pip-audit no corre
    sandbox: bool = True
    # Inicio del análisis (time.monotonic) para la duración que se guarda
    started: float = field(default_factory=time.monotonic)
    step: int = 0
    total: int = len(JOB_STEPS)
    status: str = "running"
    logs: list[str] = field(default_factory=list)
    error: dict | None = None
    commit: str | None = None
    report_id: str | None = None
    # Evento "done" ({num}) para quien siga el job desde otro worker
    done: dict | None = None
    # Lenguajes del repo (al clonar); se guardan con el análisis
    repo_languages: list[languages.Language] = field(default_factory=list)
    # Hallazgos de Bandit y pip-audit; no se guardan en la tabla `jobs` (un reintento vuelve a analizar)
    findings: list[FindingInput] = field(default_factory=list)
    listeners: set[asyncio.Queue] = field(default_factory=set)
    task: asyncio.Task | None = None
    heartbeat: asyncio.Task | None = None

    @property
    def options(self) -> dict:
        return {"sandbox": self.sandbox}

    def public(self) -> dict:
        return {
            "id": self.id, "url": self.url, "name": self.name, "branch": self.branch, "step": self.step, "total": self.total,
            "status": self.status, "logs": list(self.logs), "error": self.error, "repo_id": self.repo_id, "report_id": self.report_id,
        }


def _from_row(row: sqlite3.Row, db_path: str) -> Job:
    opts = json.loads(row["options"])
    return Job(
        id=row["id"], user_id=row["user_id"], team_id=row["team_id"], repo_id=row["repo_id"], url=row["url"], name=row["name"],
        branch=row["branch"], db_path=db_path, sandbox=opts.get("sandbox", True),
        step=row["step"], total=row["total"], status=row["status"], logs=json.loads(row["logs"]),
        error=json.loads(row["error"]) if row["error"] else None, commit=row["commit_sha"], report_id=row["report_id"],
        done=json.loads(row["done"]) if row["done"] else None,
    )


def _stale(row: sqlite3.Row) -> bool:
    return row["status"] == "running" and time.time() - row["heartbeat"] > STALE_S


class JobManager:
    def __init__(self, cloner: Cloner | None = None) -> None:
        # Jobs que corre ESTE proceso
        self._jobs: dict[str, Job] = {}
        self.cloner = cloner or Cloner()
        # Una conexión por base de datos para guardar el progreso (solo desde el hilo del event loop)
        self._conns: dict[str, sqlite3.Connection] = {}

    def _conn(self, db_path: str) -> sqlite3.Connection:
        if db_path not in self._conns:
            self._conns[db_path] = connect(db_path)
        return self._conns[db_path]

    # ─── Consulta (cualquier worker) ───

    def get(self, conn: sqlite3.Connection, job_id: str) -> Job | None:
        """El job, corra en este proceso o en otro. Uno interrumpido (sin latido) queda en error."""
        if job_id in self._jobs:
            return self._jobs[job_id]
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        if _stale(row):
            conn.execute("UPDATE jobs SET status = 'error', error = ? WHERE id = ? AND status = 'running'", (json.dumps(INTERRUPTED), job_id))
            conn.commit()
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _from_row(row, "")

    def running_for_repo(self, conn: sqlite3.Connection, repo_id: str) -> Job | None:
        local = next((j for j in self._jobs.values() if j.repo_id == repo_id and j.status == "running"), None)
        if local:
            return local
        rows = conn.execute("SELECT * FROM jobs WHERE repo_id = ? AND status = 'running'", (repo_id,)).fetchall()
        alive = [r for r in rows if not _stale(r)]
        return _from_row(alive[0], "") if alive else None

    def is_local(self, job: Job) -> bool:
        return job.id in self._jobs

    # ─── Eventos ───

    def _persist(self, job: Job) -> None:
        # Una cancelación hecha desde otro worker no se pisa
        self._conn(job.db_path).execute(
            """UPDATE jobs SET step = ?, total = ?, status = CASE WHEN status = 'cancelled' THEN status ELSE ? END, logs = ?, error = ?,
               commit_sha = ?, report_id = ?, done = ?, heartbeat = ? WHERE id = ?""",
            (job.step, job.total, job.status, json.dumps(job.logs, ensure_ascii=False), json.dumps(job.error, ensure_ascii=False) if job.error else None,
             job.commit, job.report_id, json.dumps(job.done) if job.done else None, time.time(), job.id),
        )
        self._conn(job.db_path).commit()

    def _emit(self, job: Job, msg: dict) -> None:
        if msg["type"] == "log":
            job.logs.append(msg["line"])
        self._persist(job)
        for q in job.listeners:
            q.put_nowait(msg)

    def subscribe(self, job: Job) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        q.put_nowait({"type": "snapshot", "job": job.public()})
        job.listeners.add(q)
        return q

    def unsubscribe(self, job: Job, q: asyncio.Queue) -> None:
        job.listeners.discard(q)

    async def follow_remote(self, settings: Settings, job_id: str) -> AsyncIterator[dict]:
        """Eventos de un job que corre en otro worker, reconstruidos leyendo su fila cada REMOTE_POLL_S."""
        conn = connect(settings.database_path)
        try:
            job = self.get(conn, job_id)
            yield {"type": "snapshot", "job": job.public()}
            while job.status == "running":
                await asyncio.sleep(REMOTE_POLL_S)
                new = self.get(conn, job_id)
                for line in new.logs[len(job.logs):]:
                    yield {"type": "log", "line": line}
                for i in range(job.step, new.step):
                    yield {"type": "step_done", "index": i}
                    if i + 1 < new.total and (new.status == "running" or i + 1 < new.step):
                        name, command = JOB_STEPS[i + 1]
                        yield {"type": "step", "index": i + 1, "total": new.total, "name": name, "command": command.format(branch=new.branch, url=new.url)}
                if new.status == "done" and new.done:
                    yield {"type": "done", "repo_id": new.repo_id, "report_id": new.report_id, **new.done}
                elif new.status == "error" and new.error:
                    yield {"type": "error", "step": new.step, **new.error}
                job = new
        finally:
            conn.close()

    # ─── Ciclo de vida ───

    def start(self, settings: Settings, user_id: str, team_id: str, repo_id: str, url: str, name: str, branch: str, sandbox: bool = True) -> Job:
        job = Job(
            id=f"job-{secrets.token_hex(8)}", user_id=user_id, team_id=team_id, repo_id=repo_id, url=url, name=name, branch=branch,
            db_path=settings.database_path, sandbox=sandbox, logs=[f"$ ia-voy analyze {url} --branch {branch}"],
        )
        # seed y cat: columnas de la tabla que usarán los analizadores (Sprint 5)
        self._conn(job.db_path).execute(
            """INSERT INTO jobs (id, user_id, team_id, repo_id, url, name, branch, seed, cat, options, step, total, status, logs, heartbeat, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, '{}', ?, 0, ?, 'running', ?, ?, ?)""",
            (job.id, user_id, team_id, repo_id, url, name, branch, json.dumps(job.options), job.total,
             json.dumps(job.logs, ensure_ascii=False), time.time(), now_iso()),
        )
        self._conn(job.db_path).commit()
        self._jobs[job.id] = job
        self._launch(settings, job)
        return job

    def retry(self, settings: Settings, job: Job) -> Job:
        """Reintenta en este proceso. Un job de otro worker (interrumpido) empieza de nuevo desde el clonado."""
        if not self.is_local(job):
            job.db_path = settings.database_path
            job.step = 0
            self._jobs[job.id] = job
        self._emit(job, {"type": "log", "line": "— Reintentando —"})
        job.started = time.monotonic()
        _set_repo(settings, job.repo_id, "analizando", None)
        self._launch(settings, job)
        return job

    def cancel(self, settings: Settings, job: Job) -> None:
        if job.task and not job.task.done():
            job.task.cancel()
        job.status = "cancelled"
        with session(settings.database_path) as conn:
            # Si corre en otro worker, ese proceso lo ve en su siguiente latido y lo detiene
            conn.execute("UPDATE jobs SET status = 'cancelled' WHERE id = ?", (job.id,))
            has_reports = conn.execute("SELECT 1 FROM reports WHERE repo_id = ?", (job.repo_id,)).fetchone()
        _set_repo(settings, job.repo_id, "listo" if has_reports else "error", None if has_reports else "Análisis cancelado")

    def _launch(self, settings: Settings, job: Job) -> None:
        job.status = "running"
        job.error = None
        self._persist(job)
        job.task = asyncio.create_task(self._run(settings, job))
        if job.heartbeat is None or job.heartbeat.done():
            job.heartbeat = asyncio.create_task(self._beat(job))

    async def _beat(self, job: Job) -> None:
        """Latido del job mientras corre; detiene el job si lo cancelaron desde otro worker."""
        conn = self._conn(job.db_path)
        while job.status == "running":
            await asyncio.sleep(HEARTBEAT_S)
            row = conn.execute("SELECT status FROM jobs WHERE id = ?", (job.id,)).fetchone()
            if row and row["status"] == "cancelled" and job.status == "running":
                job.status = "cancelled"
                if job.task and not job.task.done():
                    job.task.cancel()
                return
            conn.execute("UPDATE jobs SET heartbeat = ? WHERE id = ? AND status = 'running'", (time.time(), job.id))
            conn.commit()

    def _start_step(self, job: Job) -> None:
        name, command = JOB_STEPS[job.step]
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
        """Paso 1. Devuelve False si falló (el job queda en error)."""
        attempt = secrets.token_hex(4)
        token = _github_token(settings, job.user_id)
        try:
            result = await asyncio.to_thread(self.cloner.clone, settings, job.repo_id, job.url, job.branch, token, attempt)
        except CloneError as err:
            self._fail(settings, job, err)
            return False
        # Si se cancela aquí, el hilo de git termina solo y su carpeta temporal se limpia en el próximo clonado
        await asyncio.to_thread(self.cloner.promote, settings, job.repo_id, attempt)
        job.commit = result.commit
        # IA voy analiza solo Python: sin Python no hay nada que analizar; con poco, se avisa.
        # El conteo ignora dependencias y entornos subidos al repo (node_modules, venv…).
        job.repo_languages = await asyncio.to_thread(languages.detect, clone_dir(settings, job.repo_id))
        py = languages.python_files(job.repo_languages)
        with session(settings.database_path) as conn:
            conn.execute("UPDATE repos SET files = ? WHERE id = ?", (py, job.repo_id))
            import_repo_config(AnalysisStore(conn), clone_dir(settings, job.repo_id), job.repo_id)
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
        Pasos 2-5. Bandit corre en un hilo mientras el sandbox crea el entorno, instala las dependencias y
        corre pip-audit; la terminal avanza al terminar cada fase. Sin sandbox el entorno se crea en el
        backend y las dependencias no se instalan, así que pip-audit no corre. Devuelve False si el job
        quedó en error.
        """
        job.step = VENV_STEP
        runner, reason = await asyncio.to_thread(sandbox.start, settings, job.repo_id) if job.sandbox else (None, None)
        if reason:
            self._emit(job, {"type": "log", "line": f"  aviso: sandbox {settings.sandbox} no disponible ({reason}); el entorno se crea en el backend y pip-audit no corre"})
        static_task = asyncio.create_task(asyncio.to_thread(pipeline.analyze_static, settings, job.repo_id))
        try:
            # Paso 2: entorno aislado
            self._start_step(job)
            if runner:
                phase, where = await runner.wait("venv"), f"el sandbox {settings.sandbox.upper()}"
            else:
                await asyncio.sleep(settings.job_step_seconds)
                phase, where = await asyncio.to_thread(sandbox.local_venv, settings, job.repo_id), "el backend"
            if not phase.ok:
                self._fail(settings, job, CloneError(
                    "No se pudo crear el entorno aislado",
                    sandbox.summary(phase, where).strip(),
                    "Revisa que el sandbox tenga uv y Python 3.12 (o usa SANDBOX=off) y vuelve a intentarlo.",
                ))
                return False
            self._finish_step(job, sandbox.summary(phase, where))

            # Paso 3: dependencias (una instalación fallida no detiene el análisis: queda como hallazgo)
            self._start_step(job)
            install = None
            if runner:
                install = await runner.wait("install")
                summary = sandbox.install_summary(install)
            else:
                await asyncio.sleep(settings.job_step_seconds)
                summary = "  omitido: sin sandbox las dependencias del repo no se instalan en el backend"
            self._finish_step(job, summary)

            # Paso 4: Bandit
            self._start_step(job)
            static = await static_task
            self._finish_step(job, pipeline.bandit_summary(static.findings))

            # Paso 5: pip-audit
            self._start_step(job)
            findings = list(static.findings)
            if runner:
                audit = await runner.wait("audit")
                out = runner.output()
                summary = sandbox.audit_summary(audit, out)
                findings += pipeline.audit_findings(Workspace(settings, job.repo_id), static.files, out)
                if install is not None and not install.ok:
                    findings.append(pipeline.install_finding(static.files, install.log_tail))
            else:
                await asyncio.sleep(settings.job_step_seconds)
                summary = "  omitido: sin sandbox no hay dependencias instaladas que revisar"
            self._finish_step(job, summary)
            job.findings = findings
        except AnalyzerError as exc:
            self._fail(settings, job, CloneError("Bandit falló", str(exc), "Vuelve a intentarlo; si se repite, revisa el log del backend."))
            return False
        finally:
            if runner:
                runner.close()
            if not static_task.done():
                static_task.cancel()
            elif not static_task.cancelled():
                static_task.exception()  # ya se informó (o no hacía falta): que asyncio no la reporte como perdida
        return True

    async def _run(self, settings: Settings, job: Job) -> None:
        try:
            # Un reintento retoma el paso donde falló; si fue el clonado, se vuelve a clonar
            if job.step == CLONE_STEP:
                self._start_step(job)
                if not await self._clone(settings, job):
                    return
            # Un reintento a partir del entorno vuelve a correr los pasos 2-5 (el sandbox es uno solo)
            if job.step <= AUDIT_STEP and not await self._analyze(settings, job):
                return
            num = _save_report(settings, job)
            job.status = "done"
            job.done = {"num": num}
            self._emit(job, {"type": "log", "line": f"Análisis #{num} guardado en el repositorio con {len(job.findings)} hallazgo(s) de seguridad."})
            self._emit(job, {"type": "done", "repo_id": job.repo_id, "report_id": job.report_id, "num": num})
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            # Nunca dejar un job colgado en "running": el usuario ve el error y puede reintentar
            log.exception("Fallo inesperado en el job %s", job.id)
            self._fail(settings, job, CloneError("Error inesperado durante el análisis", f"{type(exc).__name__}: {exc}", "Vuelve a intentarlo; si se repite, revisa la terminal del backend."))


def _github_token(settings: Settings, user_id: str) -> str | None:
    with session(settings.database_path) as conn:
        account = GithubAccountStore(conn, Fernet(settings.token_encryption_key)).get(user_id)
    return account.token if account else None


def _set_repo(settings: Settings, repo_id: str, status: str, error: str | None) -> None:
    with session(settings.database_path) as conn:
        conn.execute("UPDATE repos SET status = ?, error = ? WHERE id = ?", (status, error, repo_id))


def _save_report(settings: Settings, job: Job) -> int:
    """Guarda el análisis en el repositorio (app.analyses.store) y devuelve su número."""
    with session(settings.database_path) as conn:
        store = AnalysisStore(conn)
        job.report_id, num = store.save_report(
            job.repo_id, branch=job.branch, commit=job.commit or "0000000", duration_s=time.monotonic() - job.started,
            languages=[{"name": lang.name, "files": lang.files} for lang in job.repo_languages],
            findings=job.findings, workspace=Workspace(settings, job.repo_id),
        )
        conn.execute("UPDATE repos SET status = 'listo', error = NULL, branch = ? WHERE id = ?", (job.branch, job.repo_id))
    return num


jobs = JobManager()
