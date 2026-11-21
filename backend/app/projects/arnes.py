"""
Configuración → Reglas de negocio → Mapa y arnés (docs/PROPUESTA_REGLAS_VERIFICABLES.md §6.2 y §7, fase 3).

- `GET  /api/projects/{id}/reglas/mapa`: mapa del proyecto (app.analyses.mapa), leído de su copia, sin IA.
- `GET  /api/projects/{id}/reglas/arnes`: el arnés guardado, su validación, la prueba de humo y si está aprobado.
- `POST /api/projects/{id}/reglas/arnes`: que Gemini lo proponga; `POST …/arnes/repo`: usar el que ya trae el repo
  (un conftest.py con `api` y `como`), sin IA.
- `PUT  /api/projects/{id}/reglas/arnes`: editarlo a mano (vuelve a pedir la prueba de humo).
- `POST /api/projects/{id}/reglas/arnes/humo`: correr la prueba de humo en el sandbox (en segundo plano).
- `POST /api/projects/{id}/reglas/arnes/aprobar`: aprobarlo; solo si la prueba de humo pasó con ese mismo código.
"""

import asyncio
import json
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app import db
from app.analyses import mapa
from app.analyses.access import Analyses, UserId, require_repo
from app.analyses.reglas_store import HarnessStore
from app.analyses.workspace import Workspace
from app.analysis import sandbox
from app.analysis.router import Config
from app.assistant.llm import LLM, LlmError
from app.assistant.router import get_llm
from app.config import Settings
from app.errors import ApiError
from app.projects import reglas_arnes as arnes
from app.projects.reglas import LLM_ERRORS

log = logging.getLogger(__name__)
router = APIRouter(tags=["reglas de negocio"])

# Pruebas de humo en marcha, por repo (se guarda la referencia para que la tarea no se pierda)
_running: dict[str, asyncio.Task] = {}


class MapSummary(BaseModel):
    framework: str | None
    frameworks: list[str]
    endpoints: int
    models: int
    schemas: int
    roles: list[str]
    # Tipos de integración (correo, sms, pagos…) y si el código usa la hora
    integrations: list[str]
    uses_time: bool
    entry: list[str]
    warnings: list[str]


class SmokeTestOut(BaseModel):
    name: str
    outcome: str
    message: str = ""


class HarnessOut(BaseModel):
    code: str
    origin: Literal["ia", "repo", "manual"]
    # conftest.py del repo del que salió (origin = repo)
    source_path: str | None
    assumptions: list[str]
    model: str | None
    commit: str | None
    updated_at: str
    fixtures: list[str]
    errors: list[str]
    warnings: list[str]
    smoke: Literal["pendiente", "corriendo", "paso", "fallo"]
    smoke_message: str | None
    smoke_tests: list[SmokeTestOut]
    smoke_at: str | None
    approved: bool
    approved_by: str | None
    approved_at: str | None


class HarnessView(BaseModel):
    cloned: bool
    map: MapSummary | None
    harness: HarnessOut | None
    # conftest.py del repo que ya sirve de arnés (define `api` y `como`)
    repo_harness: str | None
    can_generate: bool
    # Hay sandbox configurado (sin él no se puede correr la prueba de humo)
    sandbox: bool
    # Aprobado con el código actual: ya se pueden generar pruebas de reglas
    ready: bool


class HarnessCode(BaseModel):
    code: str = Field(max_length=arnes.MAX_CODE)


def _workspace(settings: Settings, repo_id: str) -> Workspace:
    ws = Workspace(settings, repo_id)
    if not ws.exists():
        raise ApiError(409, "not_cloned", "Analiza el repositorio primero: el mapa y el arnés se arman con su copia")
    return ws


def _map(ws: Workspace) -> mapa.ProjectMap:
    return mapa.build(ws.root, ws.list_files([]))


def _summary(mp: mapa.ProjectMap) -> MapSummary:
    return MapSummary(
        framework=mp.framework, frameworks=mp.frameworks, endpoints=len(mp.endpoints), models=len(mp.models), schemas=len(mp.schemas),
        roles=mp.roles, integrations=list(dict.fromkeys(i.kind for i in mp.integrations)), uses_time=bool(mp.time),
        entry=[p.name for p in mp.entry], warnings=mp.warnings,
    )


def _allowed(ws: Workspace) -> set[str]:
    return arnes.declared_imports(arnes.requirements_text(ws.root))


def _user_name(conn, user_id: str | None) -> str | None:
    if not user_id:
        return None
    row = conn.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
    return row["name"] if row else None


def _view(store: Analyses, settings: Settings, repo_id: str) -> HarnessView:
    ws = Workspace(settings, repo_id)
    if not ws.exists():
        return HarnessView(cloned=False, map=None, harness=None, repo_harness=None, can_generate=False, sandbox=settings.sandbox != "off", ready=False)
    mp = _map(ws)
    row = HarnessStore(store.conn).get(repo_id)
    out: HarnessOut | None = None
    if row:
        current = arnes.code_hash(row["code"])
        check = arnes.validate(row["code"], mp, _allowed(ws))
        smoke = row["smoke_status"] if row["smoke_hash"] == current else "pendiente"
        approved = row["approved_hash"] == current
        out = HarnessOut(
            code=row["code"], origin=row["origin"], source_path=row["source_path"], assumptions=json.loads(row["assumptions"] or "[]"),
            model=row["model"], commit=row["commit_sha"], updated_at=row["updated_at"], fixtures=check.fixtures, errors=check.errors,
            warnings=check.warnings, smoke=smoke, smoke_message=row["smoke_message"] if smoke != "pendiente" else None,
            smoke_tests=[SmokeTestOut(**t) for t in json.loads(row["smoke_tests"] or "[]")] if smoke != "pendiente" else [],
            smoke_at=row["smoke_at"] if smoke != "pendiente" else None,
            approved=approved, approved_by=_user_name(store.conn, row["approved_by"]) if approved else None,
            approved_at=row["approved_at"] if approved else None,
        )
    found = arnes.repo_harness(ws.root, mp)
    return HarnessView(
        cloned=True, map=_summary(mp), harness=out, repo_harness=found[0] if found else None,
        can_generate=bool(settings.gemini_api_key) and bool(mp.framework), sandbox=settings.sandbox != "off",
        ready=bool(out and out.approved),
    )


def _commit(store: Analyses, repo_id: str) -> str | None:
    latest = store.latest_report(repo_id)
    return latest["commit_sha"] if latest else None


@router.get("/api/projects/{project_id}/reglas/mapa")
def project_map(project_id: str, store: Analyses, user_id: UserId, settings: Config) -> dict:
    """Mapa completo del proyecto (endpoints, modelos, esquemas, roles…), para revisarlo o depurar el arnés."""
    require_repo(store, user_id, project_id)
    ws = _workspace(settings, project_id)
    return {**_map(ws).to_dict(), "commit": _commit(store, project_id)}


@router.get("/api/projects/{project_id}/reglas/arnes", response_model=HarnessView)
def get_harness(project_id: str, store: Analyses, user_id: UserId, settings: Config) -> HarnessView:
    require_repo(store, user_id, project_id)
    return _view(store, settings, project_id)


def _not_running(project_id: str) -> None:
    if project_id in _running:
        raise ApiError(409, "smoke_running", "Espera a que termine la prueba de humo del arnés")


@router.post("/api/projects/{project_id}/reglas/arnes/repo", response_model=HarnessView)
async def use_repo_harness(project_id: str, store: Analyses, user_id: UserId, settings: Config) -> HarnessView:
    """Usa el conftest.py del repo que ya es un arnés (define `api` y `como`), sin IA."""
    require_repo(store, user_id, project_id)
    _not_running(project_id)
    ws = _workspace(settings, project_id)
    mp = await asyncio.to_thread(_map, ws)
    found = arnes.repo_harness(ws.root, mp)
    if not found:
        raise ApiError(404, "no_repo_harness", "El repo no tiene un conftest.py con los fixtures `api` y `como`")
    path, code = found
    HarnessStore(store.conn).save(project_id, code, "repo", user_id, source_path=path, commit_sha=_commit(store, project_id))
    return _view(store, settings, project_id)


@router.post("/api/projects/{project_id}/reglas/arnes", response_model=HarnessView)
async def create_harness(project_id: str, store: Analyses, user_id: UserId, settings: Config, llm: Annotated[LLM, Depends(get_llm)]) -> HarnessView:
    """La IA propone el arnés con el mapa y el código del proyecto. Reemplaza al anterior y deja la prueba de humo pendiente."""
    require_repo(store, user_id, project_id)
    _not_running(project_id)
    ws = _workspace(settings, project_id)
    mp = await asyncio.to_thread(_map, ws)
    hs = HarnessStore(store.conn)
    try:
        proposed = await asyncio.to_thread(arnes.generate, llm, ws.root, mp)
    except arnes.HarnessError as exc:
        raise ApiError(422, exc.code, str(exc)) from exc
    except LlmError as exc:
        code, message = LLM_ERRORS.get(exc.kind or "", ("llm_unavailable", f"La IA no pudo proponer el arnés: {exc}"))
        raise ApiError(503, code, message) from exc
    hs.save(project_id, proposed.code, "ia", user_id, assumptions=proposed.assumptions, model=proposed.model, commit_sha=_commit(store, project_id))
    return _view(store, settings, project_id)


@router.put("/api/projects/{project_id}/reglas/arnes", response_model=HarnessView)
def edit_harness(project_id: str, body: HarnessCode, store: Analyses, user_id: UserId, settings: Config) -> HarnessView:
    """Guarda el arnés editado aunque tenga errores (se muestran); la prueba de humo no corre hasta corregirlos."""
    require_repo(store, user_id, project_id)
    _workspace(settings, project_id)
    _not_running(project_id)
    hs = HarnessStore(store.conn)
    if hs.get(project_id) is None:
        raise ApiError(404, "no_harness", "Todavía no hay arnés: propónlo con la IA o usa el del repo")
    hs.edit(project_id, body.code, user_id)
    return _view(store, settings, project_id)


@router.delete("/api/projects/{project_id}/reglas/arnes", response_model=HarnessView)
def delete_harness(project_id: str, store: Analyses, user_id: UserId, settings: Config) -> HarnessView:
    require_repo(store, user_id, project_id)
    _not_running(project_id)
    HarnessStore(store.conn).delete(project_id)
    return _view(store, settings, project_id)


async def _smoke(settings: Settings, repo_id: str, code_hash: str, files: dict[str, str]) -> None:
    """Corre la prueba de humo en el sandbox y guarda el resultado (en segundo plano)."""
    result: arnes.SmokeResult
    try:
        runner, reason = await asyncio.to_thread(sandbox.start, settings, repo_id, "arnes", files)
        if runner is None:
            result = arnes.SmokeResult("fallo", f"No se pudo usar el sandbox: {reason or 'está apagado (SANDBOX=off)'}")
        else:
            try:
                phases = {}
                for name in ("venv", "install", "tests"):
                    phase = await runner.wait(name)
                    phases[name] = (phase.code, phase.log_tail)
                out = await asyncio.to_thread(runner.output)
                result = arnes.read_smoke(out.junit, phases)
            finally:
                await asyncio.to_thread(runner.close)
    except Exception as exc:  # cualquier falla del sandbox se le muestra al equipo, no se pierde
        log.exception("Prueba de humo del arnés de %s", repo_id)
        result = arnes.SmokeResult("fallo", f"Error inesperado al correr la prueba de humo: {exc}")
    try:
        with db.session(settings.database_path) as conn:
            HarnessStore(conn).save_smoke(repo_id, code_hash, result.status, result.message, [vars(t) for t in result.tests])
    finally:
        _running.pop(repo_id, None)


@router.post("/api/projects/{project_id}/reglas/arnes/humo", response_model=HarnessView)
async def run_smoke(project_id: str, store: Analyses, user_id: UserId, settings: Config) -> HarnessView:
    """Lanza la prueba de humo (§7.4) en el sandbox. Responde enseguida con `smoke = corriendo`."""
    require_repo(store, user_id, project_id)
    ws = _workspace(settings, project_id)
    row = HarnessStore(store.conn).get(project_id)
    if row is None:
        raise ApiError(404, "no_harness", "Todavía no hay arnés: propónlo con la IA o usa el del repo")
    if project_id in _running:
        raise ApiError(409, "smoke_running", "La prueba de humo ya está corriendo")
    mp = await asyncio.to_thread(_map, ws)
    check = arnes.validate(row["code"], mp, _allowed(ws))
    if not check.valid:
        raise ApiError(422, "invalid_harness", f"Corrige el arnés antes de probarlo: {check.errors[0]}")
    if settings.sandbox == "off":
        raise ApiError(409, "sandbox_off", "La prueba de humo corre en el sandbox: configura SANDBOX=wsl o SANDBOX=docker")
    reason = await asyncio.to_thread(sandbox._available, settings)
    if reason:
        raise ApiError(409, "sandbox_unavailable", f"No se puede usar el sandbox: {reason}")
    current = arnes.code_hash(row["code"])
    HarnessStore(store.conn).running(project_id, current)
    _running[project_id] = asyncio.create_task(_smoke(settings, project_id, current, arnes.overlay(row["code"], mp)))
    return _view(store, settings, project_id)


@router.post("/api/projects/{project_id}/reglas/arnes/aprobar", response_model=HarnessView)
def approve_harness(project_id: str, store: Analyses, user_id: UserId, settings: Config) -> HarnessView:
    require_repo(store, user_id, project_id)
    view = _view(store, settings, project_id)
    if view.harness is None:
        raise ApiError(404, "no_harness", "Todavía no hay arnés: propónlo con la IA o usa el del repo")
    if view.harness.smoke != "paso":
        raise ApiError(409, "smoke_required", "Aprueba el arnés cuando su prueba de humo haya pasado con este mismo código")
    HarnessStore(store.conn).approve(project_id, arnes.code_hash(view.harness.code), user_id)
    return _view(store, settings, project_id)
