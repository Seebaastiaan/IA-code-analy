import asyncio
import json
import random
import re
import sqlite3
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.analysis.jobs import Job, JobManager, jobs, now_iso
from app.analysis.pipeline import ALL_ANALYZERS, CATEGORY_ANALYZERS
from app.auth import current_user_id
from app.config import Settings, get_settings
from app.db import connect, get_db
from app.errors import ApiError
from app.teams.store import team_id_of

router = APIRouter(tags=["analysis"])

# Solo GitHub por HTTPS: https://github.com/owner/repo(.git). Otros hosts permitirían que el servidor
# clonara direcciones internas.
REPO_URL = re.compile(r"^https://(?:www\.)?github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)(?:\.git)?/?$", re.IGNORECASE)
# Nombre de rama válido para git; sin "-" inicial para que no se interprete como opción
BRANCH = re.compile(r"^(?!-)(?!.*\.\.)[A-Za-z0-9._/-]{1,200}$")


def get_jobs() -> JobManager:
    return jobs


UserId = Annotated[str, Depends(current_user_id)]
Db = Annotated[sqlite3.Connection, Depends(get_db)]
Jobs = Annotated[JobManager, Depends(get_jobs)]
Config = Annotated[Settings, Depends(get_settings)]


class AnalyzeRequest(BaseModel):
    url: str
    branch: str = "main"
    # Vacío = todos. Si se eligen, al menos uno de cada categoría (si no, esa categoría no tendría score)
    analyzers: list[Literal["bandit", "pip-audit", "pytest", "coverage", "ruff", "radon"]] = []
    sandbox: bool = True


class JobStarted(BaseModel):
    job_id: str


def _latest_cat(conn: sqlite3.Connection, repo_id: str) -> dict | None:
    row = conn.execute("SELECT seg, test, prac FROM reports WHERE repo_id = ? ORDER BY num DESC LIMIT 1", (repo_id,)).fetchone()
    return dict(row) if row else None


CATEGORY_LABEL = {"seg": "Seguridad", "test": "Pruebas", "prac": "Buenas prácticas"}


def _analyzers(chosen: list[str]) -> list[str]:
    """Analizadores en orden canónico; 422 si alguna categoría quedó sin ninguno."""
    if not chosen:
        return list(ALL_ANALYZERS)
    missing = [CATEGORY_LABEL[c] for c, tools in CATEGORY_ANALYZERS.items() if not set(tools) & set(chosen)]
    if missing:
        raise ApiError(422, "missing_analyzers", f"Elige al menos un analizador de: {', '.join(missing)}")
    return [a for a in ALL_ANALYZERS if a in chosen]


def _start(
    conn: sqlite3.Connection, jobs: JobManager, settings: Settings, user_id: str, url: str, branch: str,
    sandbox: bool = True, analyzers: list[str] | None = None,
) -> Job:
    chosen = _analyzers(analyzers or [])
    m = REPO_URL.match(url.strip())
    if not m:
        raise ApiError(422, "invalid_url", "Usa la URL de un repositorio de GitHub (ej. https://github.com/equipo/proyecto)")
    if not BRANCH.match(branch):
        raise ApiError(422, "invalid_branch", "El nombre de la rama no es válido")
    name = f"{m.group(1)}/{m.group(2)}"
    url = f"https://github.com/{name}"
    team_id = team_id_of(conn, user_id)
    repo = conn.execute("SELECT * FROM repos WHERE team_id = ? AND name = ? COLLATE NOCASE", (team_id, name)).fetchone()
    if repo is None:
        repo_id = f"r{random.randrange(16**8):08x}"
        conn.execute(
            "INSERT INTO repos (id, team_id, user_id, name, url, branch, files, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 0, 'analizando', ?)",
            (repo_id, team_id, user_id, name, url, branch, now_iso()),
        )
    else:
        repo_id = repo["id"]
        if jobs.running_for_repo(conn, repo_id):
            raise ApiError(409, "already_running", "Ya hay un análisis en curso para este repositorio")
        conn.execute("UPDATE repos SET status = 'analizando', error = NULL, branch = ?, url = ? WHERE id = ?", (branch, url, repo_id))
    conn.commit()
    return jobs.start(
        settings, user_id, team_id, repo_id, url, repo["name"] if repo else name, branch, _latest_cat(conn, repo_id),
        sandbox=sandbox, analyzers=chosen,
    )


def _own_job(conn: sqlite3.Connection, jobs: JobManager, job_id: str, user_id: str) -> Job:
    """El job si es del equipo del usuario (corra en este proceso o en otro)."""
    job = jobs.get(conn, job_id)
    if job is None or job.team_id != team_id_of(conn, user_id):
        raise ApiError(404, "not_found", "Análisis no encontrado")
    return job


# ─── Análisis ───


@router.post("/api/analyze", response_model=JobStarted)
async def analyze(body: AnalyzeRequest, user_id: UserId, conn: Db, jobs: Jobs, settings: Config) -> JobStarted:
    job = _start(conn, jobs, settings, user_id, body.url, body.branch.strip() or "main", sandbox=body.sandbox, analyzers=list(body.analyzers))
    return JobStarted(job_id=job.id)


@router.get("/api/jobs/{job_id}")
def job_snapshot(job_id: str, user_id: UserId, jobs: Jobs, conn: Db) -> dict:
    return _own_job(conn, jobs, job_id, user_id).public()


@router.delete("/api/jobs/{job_id}", status_code=204)
def cancel_job(job_id: str, user_id: UserId, jobs: Jobs, settings: Config, conn: Db) -> Response:
    jobs.cancel(settings, _own_job(conn, jobs, job_id, user_id))
    return Response(status_code=204)


@router.post("/api/jobs/{job_id}/retry", response_model=JobStarted)
async def retry_job(job_id: str, user_id: UserId, jobs: Jobs, settings: Config, conn: Db) -> JobStarted:
    job = _own_job(conn, jobs, job_id, user_id)
    if job.status == "running":
        raise ApiError(409, "already_running", "El análisis sigue en curso")
    if job.status == "done":
        raise ApiError(409, "already_done", "El análisis ya terminó; inicia uno nuevo")
    jobs.retry(settings, job)
    return JobStarted(job_id=job.id)


@router.websocket("/ws/jobs/{job_id}")
async def job_socket(ws: WebSocket, job_id: str, jobs: Jobs, settings: Config) -> None:
    # El navegador no puede enviar Authorization en un WebSocket: el id del job (aleatorio, de 64 bits)
    # funciona como credencial de lectura del progreso.
    await ws.accept()
    conn = connect(settings.database_path)
    try:
        job = jobs.get(conn, job_id)
    finally:
        conn.close()
    if job is None:
        await ws.close(code=4404, reason="Job no encontrado")
        return
    # Corre en este proceso: eventos al instante. En otro worker: se leen de la tabla jobs.
    queue = jobs.subscribe(job) if jobs.is_local(job) else None

    async def pump() -> None:
        if queue is None:
            async for msg in jobs.follow_remote(settings, job_id):
                await ws.send_json(msg)
            return
        while True:
            await ws.send_json(await queue.get())

    async def until_closed() -> None:
        while True:
            await ws.receive_text()

    # Termina en cuanto el cliente cierra (until_closed) o falla un envío (pump)
    tasks = [asyncio.create_task(pump()), asyncio.create_task(until_closed())]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            if (exc := t.exception()) and not isinstance(exc, WebSocketDisconnect):
                raise exc
    finally:
        for t in tasks:
            t.cancel()
        if queue is not None:
            jobs.unsubscribe(job, queue)


# ─── Re-análisis ───
# Lista de repos, tablero, reporte, árbol y archivos: app.dashboard, app.reports y app.editor


@router.post("/api/repos/{repo_id}/analyze", response_model=JobStarted)
async def reanalyze(repo_id: str, user_id: UserId, conn: Db, jobs: Jobs, settings: Config) -> JobStarted:
    repo = conn.execute("SELECT * FROM repos WHERE id = ? AND team_id = ?", (repo_id, team_id_of(conn, user_id))).fetchone()
    if repo is None:
        raise ApiError(404, "not_found", "Repositorio no encontrado")
    # Mismos analizadores que el último análisis del repo
    last = conn.execute("SELECT analyzers FROM reports WHERE repo_id = ? ORDER BY num DESC LIMIT 1", (repo_id,)).fetchone()
    analyzers = json.loads(last["analyzers"] or "[]") if last else []
    return JobStarted(job_id=_start(conn, jobs, settings, user_id, repo["url"], repo["branch"], analyzers=analyzers).id)


def sandbox_service(settings: Settings) -> dict:
    """Dónde corren pytest, coverage y pip-audit (app.analysis.sandbox)."""
    if settings.sandbox == "off":
        return {"id": "sandbox", "name": "Sandbox", "role": "pytest, coverage y pip-audit simulados (SANDBOX=off)", "status": "standby", "label": "Apagado"}
    name = f"Sandbox WSL2 ({settings.sandbox_wsl_distro})" if settings.sandbox == "wsl" else "Sandbox Docker"
    return {"id": "sandbox", "name": name, "role": "Ejecuta pytest, coverage y pip-audit", "status": "ok", "label": "Activo"}


@router.get("/api/health")
def health(settings: Config) -> dict:
    github = {"status": "ok", "label": "Configurado"} if settings.github_client_id else {"status": "standby", "label": "Sin configurar"}
    return {
        "tunnel_host": None,
        "services": [
            {"id": "github", "name": "GitHub OAuth", "role": "Inicio de sesión y repos privados", **github},
            sandbox_service(settings),
            {"id": "tunnel", "name": "Cloudflare Tunnel", "role": "Acceso público", "status": "down", "label": "Inactivo"},
        ],
    }
