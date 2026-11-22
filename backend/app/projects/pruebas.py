"""
Configuración → Reglas de negocio → Pruebas de las reglas (docs/PROPUESTA_REGLAS_VERIFICABLES.md §6.3 y §9, fase 4).

- `GET  /api/projects/{id}/reglas/pruebas`: cada regla con su prueba generada, su primera corrida y si está aprobada.
- `POST /api/projects/{id}/reglas/pruebas`: generar (en segundo plano, una llamada a Gemini por regla) las de `ids`;
  sin `ids`, las reglas que no tienen prueba o cuya prueba quedó desactualizada.
- `POST …/pruebas/correr`: primera corrida en el sandbox de las pruebas en borrador (todas juntas, en segundo plano).
- `POST …/pruebas/aprobar`: aprobar las de `ids` que se pueden aprobar (corrieron con ese código y no están rotas).
- `PUT|DELETE …/pruebas/{rule_id}`: editar a mano o quitar una prueba.
- `GET  /api/projects/{id}/reglas/exportar`: zip con reglas_negocio.toml, el arnés y las pruebas aprobadas.

Fase 5 (servicios con clientes y calidad):
- `GET|PUT …/pruebas/{rule_id}/matriz`: matriz de permisos rol × acción (app.projects.reglas_matriz); al guardarla, la
  prueba sale de la tabla sin IA.
- `POST …/pruebas/{rule_id}/evidencia`: evidencia de apoyo, dónde parece estar implementada (app.projects.reglas_evidencia).
- `POST …/pruebas/fuerza`: prueba de fuerza con mutación dirigida de las que pasan (app.projects.reglas_fuerza), en
  segundo plano.

Necesita el arnés aprobado (app.projects.arnes). Solo las pruebas aprobadas cuentan en el análisis; la evidencia y la
prueba de fuerza no cambian el estado de ninguna regla.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from app import db
from app.analyses import mapa, reglas
from app.analyses.access import Analyses, UserId, require_repo
from app.analyses.analyzers import diff_patches
from app.analyses.reglas_store import EvidenceStore, RulesStore, RuleTestsStore
from app.analysis import sandbox
from app.analysis.router import Config
from app.assistant.llm import LLM, LlmError
from app.assistant.router import get_llm
from app.config import Settings
from app.editor.ai_fix import Target, ai_fix
from app.errors import ApiError
from app.projects import reglas_arnes as arnes
from app.projects import reglas_evidencia as evidencia
from app.projects import reglas_fuerza as fuerza
from app.projects import reglas_matriz as matriz
from app.projects import reglas_pruebas as pruebas
from app.projects.reglas import LLM_ERRORS

log = logging.getLogger(__name__)
router = APIRouter(tags=["reglas de negocio"])

BusyKind = Literal["generando", "corriendo", "fuerza"]


@dataclass
class Busy:
    kind: BusyKind
    total: int
    done: int = 0
    current: str | None = None
    task: asyncio.Task | None = field(default=None, repr=False)


# Trabajo en marcha por repo (generar o correr) y los avisos del último (reglas que la IA no pudo generar)
_busy: dict[str, Busy] = {}
_messages: dict[str, list[str]] = {}


# ───────────────────────── Modelos de la API ─────────────────────────


class RunTestOut(BaseModel):
    name: str
    outcome: str
    message: str = ""


class RunOut(BaseModel):
    verdict: str
    detail: str
    tests: list[RunTestOut] = Field(default_factory=list)


class SurvivorOut(BaseModel):
    file: str
    line: int
    description: str


class StrengthOut(BaseModel):
    """Prueba de fuerza: fuerte (notó todos los cambios), parcial, débil (ninguno) o no aplica."""

    status: Literal["fuerte", "parcial", "debil", "no_aplica"]
    detail: str
    killed: int
    total: int
    survivors: list[SurvivorOut]
    source: str


class PlaceOut(BaseModel):
    file: str
    start: int
    end: int
    why: str


class EvidenceOut(BaseModel):
    """Dónde parece estar implementada la regla (IA, no cuenta)."""

    verdict: Literal["implementada", "parcial", "no_encontrada"]
    summary: str
    places: list[PlaceOut]
    model: str
    search: list[str]
    created_at: str
    # Es de otra versión de la regla o de otro commit
    stale: bool


class RuleTestOut(BaseModel):
    kind: Literal["prueba", "no_implementada", "fuera_del_codigo"]
    tipo: str
    file: str
    code: str
    # ia | manual (editada a mano) | matriz (salió de la matriz de permisos, sin IA)
    origin: Literal["ia", "manual", "matriz"]
    assumptions: list[str]
    endpoints: list[str]
    reason: str | None
    model: str | None
    errors: list[str]
    warnings: list[str]
    tests: list[str]
    # La regla cambió desde que se generó (título, descripción o criterio)
    outdated: bool
    # Rutas que la prueba usa y que el código ya no tiene: el código cambió y hay que escribirla de nuevo
    gone_endpoints: list[str] = Field(default_factory=list)
    # La corrida vale para el código actual: pendiente (sin correr o editada), corriendo o hecho
    run_status: Literal["pendiente", "corriendo", "hecho"]
    run: RunOut | None
    approved: bool
    approved_by: str | None
    approved_at: str | None
    # Por qué no se puede aprobar todavía (None = se puede)
    blocked: str | None
    updated_at: str
    # Prueba de fuerza del código actual: pendiente (no se ha hecho o la prueba cambió), corriendo o hecho
    strength_status: Literal["pendiente", "corriendo", "hecho"]
    strength: StrengthOut | None
    # Se puede hacer la prueba de fuerza (pasa con el código actual); si no, por qué
    strength_blocked: str | None
    # La prueba salió de una matriz de permisos guardada
    has_matrix: bool


class CrosscheckOut(BaseModel):
    """Dos comprobaciones que no se ven entre sí: la prueba corrida y la IA leyendo el código sin ver la prueba."""

    status: Literal["coincide", "discrepa", "sin_revisar"]
    note: str


class RuleRow(BaseModel):
    id: str
    title: str
    description: str
    severity: str
    criterion: str | None
    # Pruebas del repo que ya verifican la regla: tienen prioridad sobre la generada
    repo_tests: int
    state: Literal["sin_prueba", "borrador", "aprobada", "desactualizada"]
    test: RuleTestOut | None
    # La regla habla de permisos o roles (o su prueba es de tipo permisos): se le ofrece la matriz
    permissions: bool
    evidence: EvidenceOut | None
    # Contraste entre la prueba y la lectura independiente del código (no cuenta en el score)
    crosscheck: CrosscheckOut


class BusyOut(BaseModel):
    kind: BusyKind
    total: int
    done: int
    current: str | None


class TestsView(BaseModel):
    cloned: bool
    # De dónde salen las reglas: reglas_negocio.toml del repo o las cargadas en la app
    source: str | None
    error: str | None
    harness_ready: bool
    can_generate: bool
    # Hay clave de Gemini para pedir la evidencia de apoyo
    can_explain: bool
    sandbox: bool
    rules: list[RuleRow]
    busy: BusyOut | None
    messages: list[str]


class Ids(BaseModel):
    ids: list[str] | None = Field(default=None, max_length=reglas.MAX_RULES)


class TestCode(BaseModel):
    code: str = Field(max_length=pruebas.MAX_CODE)


class ActionOut(BaseModel):
    id: str
    method: str
    path: str
    function: str
    # Roles que el código deja pasar hoy (lo que leyó el mapa): sugerencia, no oráculo
    suggested: list[str]
    cells: dict[str, Literal["permitido", "prohibido"]]


class MatrixOut(BaseModel):
    rule_id: str
    roles: list[str]
    actions: list[ActionOut]
    # Ya hay una matriz guardada para la regla
    saved: bool


class MatrixIn(BaseModel):
    # acción ("PATCH /servicios/{id}") → rol → permitido | prohibido | null (fuera de la matriz)
    cells: dict[str, dict[str, Literal["permitido", "prohibido"] | None]] = Field(max_length=matriz.MAX_ACTIONS)


# ───────────────────────── Estado ─────────────────────────


def _blocked(row, check: pruebas.TestCheck | None, outdated: bool, run_current: bool, run: dict | None) -> str | None:
    if outdated:
        return "La regla cambió: vuelve a generar la prueba"
    if row["kind"] != "prueba":
        return None
    if check and check.errors:
        return "Corrige los errores de la prueba"
    if not run_current or run is None:
        return "Córrela primero en el sandbox"
    if run.get("verdict") == "prueba_rota":
        return "La prueba está rota: corrígela o vuelve a generarla"
    return None


def _strength_blocked(row, outdated: bool, run_current: bool, run: dict | None) -> str | None:
    if row["kind"] != "prueba" or outdated:
        return "Solo para pruebas al día"
    if not run_current or run is None:
        return "Córrela primero en el sandbox"
    if run.get("verdict") != "cumple":
        return "Solo para pruebas que pasan: si la prueba falla, el código no cumple y no hay nada que medir"
    return None


def _commit(conn, repo_id: str) -> str | None:
    from app.analyses.store import AnalysisStore

    latest = AnalysisStore(conn).latest_report(repo_id)
    return latest["commit_sha"] if latest else None


def _evidence(row, rule: reglas.BusinessRule, commit: str | None) -> EvidenceOut | None:
    ev = evidencia.loads(row["data"]) if row else None
    if ev is None:
        return None
    stale = row["rule_hash"] != pruebas.rule_hash(rule) or (commit is not None and row["commit_sha"] != commit)
    return EvidenceOut(
        verdict=ev.verdict, summary=ev.summary, places=[PlaceOut(**vars(p)) for p in ev.places], model=ev.model, search=ev.search,
        created_at=row["created_at"], stale=stale,
    )


# (resultado de la prueba, lectura del código) → ¿coinciden? Una prueba que pasa con un código que «no se encuentra» o
# «parcial» es sospechosa (prueba floja); una que falla con un código «implementado» también (prueba mal escrita).
CROSS_AGREE = {
    ("cumple", "implementada"): "La prueba pasa y la lectura del código confirma que la regla está implementada.",
    ("no_cumple", "no_encontrada"): "La prueba falla y la lectura no encuentra la regla en el código: probablemente no está implementada.",
    ("no_cumple", "parcial"): "La prueba falla y la lectura ve la regla solo en parte: falta cubrir algo.",
}
CROSS_DISAGREE = {
    ("cumple", "parcial"): "La prueba pasa, pero la lectura del código dice que la regla solo se cumple en parte: la prueba puede ser floja.",
    ("cumple", "no_encontrada"): "La prueba pasa, pero no se encontró dónde el código implementa la regla: la prueba puede no comprobar lo que dice.",
    ("no_cumple", "implementada"): "La prueba falla, pero el código parece implementar la regla: la prueba puede estar mal escrita.",
}


def crosscheck(run: RunOut | None, evidence: EvidenceOut | None) -> CrosscheckOut:
    """Contrasta el resultado de la prueba con la lectura independiente del código."""
    if run is None or run.verdict not in ("cumple", "no_cumple"):
        return CrosscheckOut(status="sin_revisar", note="Falta una prueba que corra y dé un resultado claro.")
    if evidence is None or evidence.stale:
        return CrosscheckOut(status="sin_revisar", note="Falta leer el código de forma independiente (o la lectura es de una versión anterior).")
    key = (run.verdict, evidence.verdict)
    if key in CROSS_AGREE:
        return CrosscheckOut(status="coincide", note=CROSS_AGREE[key])
    return CrosscheckOut(status="discrepa", note=CROSS_DISAGREE[key])


def _view(conn, settings: Settings, repo_id: str) -> TestsView:
    ctx = pruebas.context(conn, settings, repo_id)
    busy = _busy.get(repo_id)
    base = {
        "cloned": ctx.ws.exists(), "source": ctx.source, "error": ctx.error, "harness_ready": ctx.harness_ready,
        "can_generate": bool(settings.gemini_api_key) and ctx.harness_ready, "can_explain": bool(settings.gemini_api_key),
        "sandbox": settings.sandbox != "off",
        "busy": BusyOut(kind=busy.kind, total=busy.total, done=busy.done, current=busy.current) if busy else None,
        "messages": _messages.get(repo_id, []),
    }
    if not ctx.ws.exists() or not ctx.rules:
        return TestsView(**base, rules=[])
    mp = mapa.build(ctx.ws.root, ctx.ws.list_files([]))
    fixtures = arnes.fixtures_of(ctx.harness or "")
    allowed = arnes.declared_imports(arnes.requirements_text(ctx.ws.root))
    files = ctx.ws.list_files([])
    declared = reglas.declared_tests(files, ctx.ws.read_lines)
    stored = {r["rule_id"]: r for r in RuleTestsStore(conn).all(repo_id)}
    evidences = EvidenceStore(conn).all(repo_id)
    commit = _commit(conn, repo_id)
    names = {r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM users").fetchall()}
    rows: list[RuleRow] = []
    for rule in ctx.rules:
        row = stored.get(rule.id)
        test: RuleTestOut | None = None
        state = "sin_prueba"
        if row:
            current = arnes.code_hash(row["code"])
            outdated = row["rule_hash"] != pruebas.rule_hash(rule)
            check = pruebas.validate(row["code"], rule.id, mp, fixtures, allowed) if row["kind"] == "prueba" else None
            run_current = row["run_hash"] == current
            run_status = row["run_status"] if run_current else "pendiente"
            run = json.loads(row["run_result"]) if run_current and row["run_result"] else None
            approved = row["approved_hash"] == current and not outdated
            strength_current = row["strength_hash"] == current
            strength = fuerza.loads(row["strength_result"]) if strength_current and row["strength_status"] == "hecho" else None
            test = RuleTestOut(
                kind=row["kind"], tipo=row["tipo"], file=row["file"], code=row["code"], origin=row["origin"],
                assumptions=json.loads(row["assumptions"] or "[]"), endpoints=json.loads(row["endpoints"] or "[]"), reason=row["reason"],
                model=row["model"], errors=check.errors if check else [], warnings=check.warnings if check else [],
                tests=check.tests if check else [], outdated=outdated, run_status=run_status,
                gone_endpoints=pruebas.missing_endpoints(json.loads(row["endpoints"] or "[]"), mp) if row["kind"] == "prueba" else [],
                run=RunOut(**run) if run else None, approved=approved,
                approved_by=names.get(row["approved_by"]) if approved else None, approved_at=row["approved_at"] if approved else None,
                blocked=_blocked(row, check, outdated, run_current and run_status == "hecho", run), updated_at=row["updated_at"],
                strength_status=(row["strength_status"] or "pendiente") if strength_current else "pendiente",
                strength=StrengthOut(**strength.to_dict()) if strength else None,
                strength_blocked=_strength_blocked(row, outdated, run_current and run_status == "hecho", run), has_matrix=bool(row["matrix"]),
            )
            state = "desactualizada" if outdated else "aprobada" if approved else "borrador"
        evidence = _evidence(evidences.get(rule.id), rule, commit)
        rows.append(RuleRow(
            id=rule.id, title=rule.title, description=rule.description, severity=rule.severity, criterion=rule.criterion,
            repo_tests=sum(rule.id in t.rules for t in declared), state=state, test=test,
            permissions=matriz.looks_like_permissions(rule) or bool(row and row["tipo"] == "permisos"),
            evidence=evidence, crosscheck=crosscheck(test.run if test else None, evidence),
        ))
    return TestsView(**base, rules=rows)


def _require_free(repo_id: str) -> None:
    busy = _busy.get(repo_id)
    if busy:
        what = {"generando": "generando pruebas", "corriendo": "corriendo las pruebas", "fuerza": "haciendo la prueba de fuerza"}[busy.kind]
        raise ApiError(409, "tests_busy", f"Espera: IA voy está {what} de este proyecto")


# ───────────────────────── Generar ─────────────────────────


def broken_of(settings: Settings, repo_id: str, rule: reglas.BusinessRule) -> tuple[str, str] | None:
    """(código, por qué se rompió) si la prueba actual de la regla se corrió y se rompió al preparar el escenario."""
    with db.session(settings.database_path) as conn:
        row = RuleTestsStore(conn).get(repo_id, rule.id)
    if row is None or row["kind"] != "prueba" or row["rule_hash"] != pruebas.rule_hash(rule) or not row["run_result"]:
        return None
    if row["run_hash"] != arnes.code_hash(row["code"]):
        return None
    run = json.loads(row["run_result"])
    if run.get("verdict") != "prueba_rota":
        return None
    why = [f"{t.get('name')}: {t.get('message')}" for t in run.get("tests") or [] if t.get("message")]
    return row["code"], "\n".join(why) or str(run.get("detail") or "")


async def _generate(settings: Settings, repo_id: str, llm: LLM, ids: list[str], user_id: str) -> None:
    busy = _busy[repo_id]
    messages: list[str] = []
    try:
        with db.session(settings.database_path) as conn:
            ctx = pruebas.context(conn, settings, repo_id)
        mp = await asyncio.to_thread(mapa.build, ctx.ws.root, ctx.ws.list_files([]))
        by_id = {r.id: r for r in ctx.rules}
        allowed = arnes.declared_imports(arnes.requirements_text(ctx.ws.root))
        for rid in ids:
            rule = by_id.get(rid)
            busy.current = rid
            if rule is None or ctx.harness is None:
                continue
            try:
                g = await asyncio.to_thread(pruebas.generate, llm, ctx.ws.root, mp, ctx.harness, rule, allowed, broken_of(settings, repo_id, rule))
            except pruebas.GenerationError as exc:
                messages.append(f"{rid}: {exc}")
                continue
            except LlmError as exc:
                messages.append(f"{rid}: {LLM_ERRORS.get(exc.kind or '', ('', f'la IA falló ({exc})'))[1]}")
                if exc.rate_limited:
                    messages.append("Se detuvo la generación: vuelve a intentarlo en un minuto con las que faltan.")
                    break
                continue
            with db.session(settings.database_path) as conn:
                RuleTestsStore(conn).save(
                    repo_id, rid, pruebas.rule_hash(rule), kind=g.kind, tipo=g.tipo, file=pruebas.test_path(rule), code=g.code, origin="ia",
                    user_id=user_id, assumptions=g.assumptions, endpoints=g.endpoints, reason=g.reason or None, model=g.model,
                )
            busy.done += 1
    except Exception as exc:  # cualquier falla se le muestra al equipo, no se pierde
        log.exception("Generación de pruebas de %s", repo_id)
        messages.append(f"Error inesperado al generar las pruebas: {exc}")
    finally:
        _messages[repo_id] = messages
        _busy.pop(repo_id, None)


@router.post("/api/projects/{project_id}/reglas/pruebas", response_model=TestsView)
async def generate_tests(project_id: str, body: Ids, store: Analyses, user_id: UserId, settings: Config, llm: Annotated[LLM, Depends(get_llm)]) -> TestsView:
    """Genera en segundo plano las pruebas de `ids` (o de las reglas sin prueba o desactualizadas). Responde enseguida."""
    require_repo(store, user_id, project_id)
    _require_free(project_id)
    ctx = pruebas.context(store.conn, settings, project_id)
    if not ctx.ws.exists():
        raise ApiError(409, "not_cloned", "Analiza el repositorio primero")
    if not ctx.harness_ready:
        raise ApiError(409, "harness_not_ready", "Aprueba el arnés de pruebas primero (Mapa y arnés de pruebas)")
    if not ctx.rules:
        raise ApiError(409, "no_rules", ctx.error or "El proyecto no tiene reglas de negocio válidas")
    stored = {r["rule_id"]: r for r in RuleTestsStore(store.conn).all(project_id)}
    known = {r.id for r in ctx.rules}
    if body.ids is not None:
        unknown = [i for i in body.ids if i not in known]
        if unknown:
            raise ApiError(404, "unknown_rule", f"{', '.join(unknown)} no está en las reglas del proyecto")
        ids = list(dict.fromkeys(body.ids))
    else:
        ids = [r.id for r in ctx.rules if r.id not in stored or stored[r.id]["rule_hash"] != pruebas.rule_hash(r)]
    if not ids:
        raise ApiError(409, "nothing_to_generate", "Todas las reglas ya tienen prueba; elige cuáles volver a generar")
    ids = ids[: pruebas.MAX_GENERATE]
    _messages.pop(project_id, None)
    _busy[project_id] = Busy("generando", len(ids))
    _busy[project_id].task = asyncio.create_task(_generate(settings, project_id, llm, ids, user_id))
    return _view(store.conn, settings, project_id)


# ───────────────────────── Correr ─────────────────────────


async def _run(settings: Settings, repo_id: str, harness: str, files: dict[str, str], hashes: dict[str, str], rules: list[reglas.BusinessRule]) -> None:
    results: dict[str, pruebas.RunResult]
    try:
        runner, reason = await asyncio.to_thread(sandbox.start, settings, repo_id, "pruebas", pruebas.overlay(harness, files))
        if runner is None:
            problem = f"No se pudo usar el sandbox: {reason or 'está apagado (SANDBOX=off)'}"
            results = {r.id: pruebas.RunResult("prueba_rota", problem) for r in rules}
        else:
            try:
                phases = {}
                for name in ("venv", "install", "tests"):
                    phase = await runner.wait(name)
                    phases[name] = (phase.code, phase.log_tail)
                out = await asyncio.to_thread(runner.output)
                results = pruebas.read_run(out.reglas, phases, rules)
            finally:
                await asyncio.to_thread(runner.close)
    except Exception as exc:  # cualquier falla se le muestra al equipo, no se pierde
        log.exception("Corrida de pruebas de %s", repo_id)
        results = {r.id: pruebas.RunResult("prueba_rota", f"Error inesperado al correr las pruebas: {exc}") for r in rules}
    try:
        with db.session(settings.database_path) as conn:
            RuleTestsStore(conn).save_run(repo_id, {rid: (hashes[rid], results[rid].to_dict()) for rid in hashes if rid in results})
    finally:
        _busy.pop(repo_id, None)


@router.post("/api/projects/{project_id}/reglas/pruebas/correr", response_model=TestsView)
async def run_tests(project_id: str, body: Ids, store: Analyses, user_id: UserId, settings: Config) -> TestsView:
    """Corre en el sandbox las pruebas de `ids` (o todas las válidas sin correr). Responde enseguida."""
    require_repo(store, user_id, project_id)
    _require_free(project_id)
    view = _view(store.conn, settings, project_id)
    ctx = pruebas.context(store.conn, settings, project_id)
    if not ctx.harness_ready or ctx.harness is None:
        raise ApiError(409, "harness_not_ready", "Aprueba el arnés de pruebas primero (Mapa y arnés de pruebas)")
    if settings.sandbox == "off":
        raise ApiError(409, "sandbox_off", "Las pruebas corren en el sandbox: configura SANDBOX=wsl o SANDBOX=docker")
    wanted = set(body.ids) if body.ids is not None else None
    chosen = [
        r for r in view.rules
        if r.test and r.test.kind == "prueba" and not r.test.errors and not r.test.outdated
        and (r.id in wanted if wanted is not None else r.test.run_status == "pendiente")
    ]
    if not chosen:
        raise ApiError(409, "nothing_to_run", "No hay pruebas válidas sin correr; elige cuáles volver a correr")
    reason = await asyncio.to_thread(sandbox._available, settings)
    if reason:
        raise ApiError(409, "sandbox_unavailable", f"No se puede usar el sandbox: {reason}")
    files = {r.test.file: r.test.code for r in chosen if r.test}
    hashes = {r.id: arnes.code_hash(r.test.code) for r in chosen if r.test}
    by_id = {r.id: r for r in ctx.rules}
    RuleTestsStore(store.conn).running(project_id, hashes)
    _busy[project_id] = Busy("corriendo", len(chosen))
    _busy[project_id].task = asyncio.create_task(_run(settings, project_id, ctx.harness, files, hashes, [by_id[r.id] for r in chosen]))
    return _view(store.conn, settings, project_id)


# ───────────────────────── Aprobar, editar, quitar ─────────────────────────


@router.get("/api/projects/{project_id}/reglas/pruebas", response_model=TestsView)
def list_tests(project_id: str, store: Analyses, user_id: UserId, settings: Config) -> TestsView:
    require_repo(store, user_id, project_id)
    if project_id not in _busy:
        RuleTestsStore(store.conn).reset_running(project_id)
    return _view(store.conn, settings, project_id)


@router.post("/api/projects/{project_id}/reglas/pruebas/aprobar", response_model=TestsView)
def approve_tests(project_id: str, body: Ids, store: Analyses, user_id: UserId, settings: Config) -> TestsView:
    """Aprueba las de `ids` que se pueden aprobar; de las demás dice por qué no (en `messages`)."""
    require_repo(store, user_id, project_id)
    _require_free(project_id)
    view = _view(store.conn, settings, project_id)
    wanted = set(body.ids or [])
    skipped: list[str] = []
    ts = RuleTestsStore(store.conn)
    for r in view.rules:
        if r.id not in wanted or r.test is None or r.test.approved:
            continue
        if r.test.blocked:
            skipped.append(f"{r.id}: {r.test.blocked}")
            continue
        ts.approve(project_id, r.id, arnes.code_hash(r.test.code), user_id)
    _messages[project_id] = skipped
    return _view(store.conn, settings, project_id)


@router.put("/api/projects/{project_id}/reglas/pruebas/{rule_id}", response_model=TestsView)
def edit_test(project_id: str, rule_id: str, body: TestCode, store: Analyses, user_id: UserId, settings: Config) -> TestsView:
    """Guarda la prueba editada (aunque tenga errores, que se muestran); hay que volver a correrla y aprobarla."""
    require_repo(store, user_id, project_id)
    _require_free(project_id)
    ts = RuleTestsStore(store.conn)
    if ts.get(project_id, rule_id) is None:
        raise ApiError(404, "no_test", f"{rule_id} todavía no tiene prueba: genérala primero")
    ts.edit(project_id, rule_id, body.code, user_id)
    return _view(store.conn, settings, project_id)


@router.delete("/api/projects/{project_id}/reglas/pruebas/{rule_id}", response_model=TestsView)
def delete_test(project_id: str, rule_id: str, store: Analyses, user_id: UserId, settings: Config) -> TestsView:
    require_repo(store, user_id, project_id)
    _require_free(project_id)
    RuleTestsStore(store.conn).delete(project_id, rule_id)
    return _view(store.conn, settings, project_id)


@router.get("/api/projects/{project_id}/reglas/exportar")
def export(project_id: str, store: Analyses, user_id: UserId, settings: Config) -> Response:
    """reglas_negocio.toml + tests/reglas/conftest.py (el arnés) + las pruebas aprobadas, para hacer commit en el repo."""
    repo = require_repo(store, user_id, project_id)
    view = _view(store.conn, settings, project_id)
    ctx = pruebas.context(store.conn, settings, project_id)
    if not ctx.text:
        raise ApiError(409, "no_rules", ctx.error or "El proyecto no tiene reglas de negocio válidas")
    tests = {r.test.file: r.test.code for r in view.rules if r.test and r.test.approved and r.test.kind == "prueba"}
    data = pruebas.export_zip(ctx.text, ctx.harness if ctx.harness_ready else None, tests)
    name = repo["name"].split("/")[-1] or "proyecto"
    return Response(data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="reglas-{name}.zip"'})


# ───────────────────────── Fase 5: matriz de permisos ─────────────────────────


def _rule(ctx: pruebas.Context, rule_id: str) -> reglas.BusinessRule:
    if not ctx.ws.exists():
        raise ApiError(409, "not_cloned", "Analiza el repositorio primero")
    rule = next((r for r in ctx.rules if r.id == rule_id), None)
    if rule is None:
        raise ApiError(404, "unknown_rule", f"{rule_id} no está en las reglas del proyecto")
    return rule


@router.get("/api/projects/{project_id}/reglas/pruebas/{rule_id}/matriz", response_model=MatrixOut)
def get_matrix(project_id: str, rule_id: str, store: Analyses, user_id: UserId, settings: Config) -> MatrixOut:
    """La matriz rol × acción de la regla: la guardada sobre las acciones del mapa de hoy, o vacía con sugerencias."""
    require_repo(store, user_id, project_id)
    ctx = pruebas.context(store.conn, settings, project_id)
    rule = _rule(ctx, rule_id)
    mp = mapa.build(ctx.ws.root, ctx.ws.list_files([]))
    row = RuleTestsStore(store.conn).get(project_id, rule.id)
    saved = json.loads(row["matrix"]) if row and row["matrix"] else None
    m = matriz.from_dict(saved, mp)
    if not m.roles:
        raise ApiError(409, "no_roles", "El mapa del proyecto no encontró roles: la matriz necesita los roles (escribe la prueba a mano)")
    return MatrixOut(rule_id=rule.id, roles=m.roles, actions=[ActionOut(**vars(a)) for a in m.actions], saved=saved is not None)


@router.put("/api/projects/{project_id}/reglas/pruebas/{rule_id}/matriz", response_model=TestsView)
def save_matrix(project_id: str, rule_id: str, body: MatrixIn, store: Analyses, user_id: UserId, settings: Config) -> TestsView:
    """Guarda la matriz y escribe su prueba sin IA (reemplaza la prueba de la regla); hay que correrla y aprobarla."""
    require_repo(store, user_id, project_id)
    _require_free(project_id)
    ctx = pruebas.context(store.conn, settings, project_id)
    rule = _rule(ctx, rule_id)
    if not ctx.harness_ready:
        raise ApiError(409, "harness_not_ready", "Aprueba el arnés de pruebas primero (Mapa y arnés de pruebas)")
    mp = mapa.build(ctx.ws.root, ctx.ws.list_files([]))
    try:
        m = matriz.update(mp, body.cells)
        code = matriz.test_code(rule, m, mp.framework)
    except matriz.MatrixError as exc:
        raise ApiError(422, exc.code, str(exc)) from exc
    cases = m.cases()
    allowed = sum(1 for *_, ok in cases if ok)
    RuleTestsStore(store.conn).save(
        project_id, rule.id, pruebas.rule_hash(rule), kind="prueba", tipo="permisos", file=pruebas.test_path(rule), code=code,
        origin="matriz", user_id=user_id, endpoints=[a.id for a in m.actions if a.cells],
        assumptions=[
            f"La matriz del equipo: {len(cases)} celdas ({allowed} permitidas, {len(cases) - allowed} prohibidas)",
            "Las rutas apuntan a un registro que no existe: se asume que el permiso se revisa antes de buscarlo",
        ],
        matrix=m.to_dict(),
    )
    return _view(store.conn, settings, project_id)


# ───────────────────────── Fase 5: evidencia de apoyo ─────────────────────────


@router.post("/api/projects/{project_id}/reglas/pruebas/{rule_id}/evidencia", response_model=TestsView)
async def explain_rule(
    project_id: str, rule_id: str, store: Analyses, user_id: UserId, settings: Config, llm: Annotated[LLM, Depends(get_llm)],
) -> TestsView:
    """Pide a la IA dónde parece estar implementada la regla (una llamada). No cambia su estado ni el score."""
    require_repo(store, user_id, project_id)
    if not settings.gemini_api_key:
        raise ApiError(409, "no_llm", "La evidencia de apoyo usa la IA: configura GEMINI_API_KEY")
    ctx = pruebas.context(store.conn, settings, project_id)
    rule = _rule(ctx, rule_id)
    mp = await asyncio.to_thread(mapa.build, ctx.ws.root, ctx.ws.list_files([]))
    hits = await asyncio.to_thread(evidencia.index_hits, store.conn, llm, project_id, rule)
    try:
        ev = await asyncio.to_thread(evidencia.collect, llm, ctx.ws.root, mp, rule, hits)
    except LlmError as exc:
        code, message = LLM_ERRORS.get(exc.kind or "", ("llm_unavailable", f"La IA no pudo revisar el código: {exc}"))
        raise ApiError(503, code, message) from exc
    EvidenceStore(store.conn).save(project_id, rule.id, pruebas.rule_hash(rule), _commit(store.conn, project_id), ev.to_dict(), user_id)
    return _view(store.conn, settings, project_id)


# ───────────────────────── El documento manda: corregir el código ─────────────────────────

# Lugares del código que se proponen corregir a la vez, y estados en que el código viola la regla
MAX_FIX_PLACES = 3
VIOLATED = ("no_cumple", "no_implementada")


class RuleFix(BaseModel):
    patches: list[dict]
    notes: list[str] = Field(default_factory=list)
    # Los lugares del código que se corrigieron («archivo:línea»)
    places: list[str]


@router.post("/api/projects/{project_id}/reglas/pruebas/{rule_id}/corregir", response_model=RuleFix)
async def fix_code_for_rule(
    project_id: str, rule_id: str, store: Analyses, user_id: UserId, settings: Config, llm: Annotated[LLM, Depends(get_llm)],
) -> RuleFix:
    """
    Caso 2 del plan de reglas automáticas: el código y el documento se contradicen y **el documento manda**. La IA propone
    el cambio mínimo en el código para que cumpla la regla; nunca toca la regla ni su prueba. Nada se guarda: el editor
    muestra el diff y la persona decide.
    """
    require_repo(store, user_id, project_id)
    if not settings.gemini_api_key:
        raise ApiError(409, "no_llm", "Las correcciones con IA necesitan GEMINI_API_KEY en backend/.env")
    ctx = pruebas.context(store.conn, settings, project_id)
    rule = _rule(ctx, rule_id)
    latest = store.latest_report(project_id)
    result = next((r for r in RulesStore(store.conn).results(latest["id"]) if r["rule_id"] == rule_id), None) if latest else None
    if result is None or result["status"] not in VIOLATED:
        raise ApiError(409, "not_violated", f"{rule_id} no aparece como incumplida en el último análisis: no hay nada que corregir")

    # Dónde corregir: el patrón que la regla prohíbe, o dónde parece estar implementada según la IA
    places: list[tuple[str, int]] = [(e["file"], int(e["line"])) for e in json.loads(result["evidence"] or "[]")]
    if not places:
        saved = EvidenceStore(store.conn).get(project_id, rule_id)
        ev = evidencia.loads(saved["data"]) if saved and saved["rule_hash"] == pruebas.rule_hash(rule) else None
        if ev is None:
            mp = await asyncio.to_thread(mapa.build, ctx.ws.root, ctx.ws.list_files([]))
            hits = await asyncio.to_thread(evidencia.index_hits, store.conn, llm, project_id, rule)
            try:
                ev = await asyncio.to_thread(evidencia.collect, llm, ctx.ws.root, mp, rule, hits)
            except LlmError as exc:
                code, message = LLM_ERRORS.get(exc.kind or "", ("llm_unavailable", f"La IA no pudo revisar el código: {exc}"))
                raise ApiError(503, code, message) from exc
            EvidenceStore(store.conn).save(project_id, rule_id, pruebas.rule_hash(rule), _commit(store.conn, project_id), ev.to_dict(), user_id)
        places = [(p.file, p.start) for p in ev.places]
    places = list(dict.fromkeys(places))[:MAX_FIX_PLACES]
    if not places:
        raise ApiError(422, "no_place", f"No encontré en el código dónde corregir {rule_id}: ábrelo en el editor o pregúntale a la IA en el asistente")

    msg = f"La regla {rule.id} «{rule.title}» no se cumple en el código: {rule.description}"
    others = "; ".join(f"{r.id} «{r.title}»" for r in ctx.rules if r.id != rule.id)[:3000]
    rec = (
        "El documento de requisitos manda: cambia el CÓDIGO para que cumpla la regla. No cambies la regla ni sus pruebas. "
        "Haz el cambio MÍNIMO: si basta con corregir un operador de comparación o un valor, cambia solo eso y conserva las "
        "variables, constantes y condiciones que ya existen (excepciones, roles, casos especiales). "
        f"Estas otras reglas deben seguir cumpliéndose, no las rompas: {others or 'ninguna'}."
    )
    by_file: dict[str, list[int]] = {}
    for path, line in places:
        by_file.setdefault(path, []).append(line)
    patches: list[dict] = []
    notes: list[str] = []
    for path, lines in by_file.items():
        try:
            content = ctx.ws.read(path)
        except (OSError, ApiError):
            continue
        targets = [Target(0, "Regla de negocio", rule.id, line, msg, rec) for line in lines]
        try:
            fixed, note = await asyncio.to_thread(ai_fix, llm, path, content, targets)
        except LlmError as exc:
            code, message = LLM_ERRORS.get(exc.kind or "", ("llm_unavailable", f"La IA no pudo proponer la corrección: {exc}"))
            raise ApiError(503, code, message) from exc
        except ApiError as exc:
            if exc.status == 409:
                continue
            raise
        patches += diff_patches(path, content, fixed)
        if note:
            notes.append(f"{path}: {note}")
    if not patches:
        raise ApiError(409, "fix_unavailable", f"La IA no encontró un cambio en el código que cumpla {rule_id}: revísalo a mano")
    return RuleFix(patches=patches, notes=notes, places=[f"{p}:{n}" for p, n in places])


# ───────────────────────── Fase 5: prueba de fuerza ─────────────────────────

Plan = dict[str, tuple[list[fuerza.Mutant], list[fuerza.Target]]]


async def _strength(settings: Settings, repo_id: str, files: dict[str, str], hashes: dict[str, str], plan: Plan) -> None:
    results: dict[str, fuerza.StrengthResult]
    try:
        runner, reason = await asyncio.to_thread(sandbox.start, settings, repo_id, "fuerza", files)
        if runner is None:
            problem = f"No se pudo usar el sandbox: {reason or 'está apagado (SANDBOX=off)'}"
            results = {rid: fuerza.StrengthResult("no_aplica", problem) for rid in plan}
        else:
            try:
                phases = {}
                for name in ("venv", "install", "tests"):
                    phase = await runner.wait(name)
                    phases[name] = (phase.code, phase.log_tail)
                out = await asyncio.to_thread(runner.output)
                results = fuerza.read(out.fuerza, phases, plan)
            finally:
                await asyncio.to_thread(runner.close)
    except Exception as exc:  # cualquier falla se le muestra al equipo, no se pierde
        log.exception("Prueba de fuerza de %s", repo_id)
        results = {rid: fuerza.StrengthResult("no_aplica", f"Error inesperado en la prueba de fuerza: {exc}") for rid in plan}
    try:
        with db.session(settings.database_path) as conn:
            RuleTestsStore(conn).save_strength(repo_id, {rid: (hashes[rid], results[rid].to_dict()) for rid in hashes if rid in results})
    finally:
        _busy.pop(repo_id, None)


@router.post("/api/projects/{project_id}/reglas/pruebas/fuerza", response_model=TestsView)
async def strength_tests(project_id: str, body: Ids, store: Analyses, user_id: UserId, settings: Config) -> TestsView:
    """
    Prueba de fuerza de `ids` (o de las que pasan y no la tienen): cambia a propósito las líneas de la regla y comprueba
    que la prueba lo nota. En segundo plano, en el sandbox. No cambia el estado de la regla.
    """
    require_repo(store, user_id, project_id)
    _require_free(project_id)
    view = _view(store.conn, settings, project_id)
    ctx = pruebas.context(store.conn, settings, project_id)
    if not ctx.harness_ready or ctx.harness is None:
        raise ApiError(409, "harness_not_ready", "Aprueba el arnés de pruebas primero (Mapa y arnés de pruebas)")
    if settings.sandbox == "off":
        raise ApiError(409, "sandbox_off", "La prueba de fuerza corre en el sandbox: configura SANDBOX=wsl o SANDBOX=docker")
    wanted = set(body.ids) if body.ids is not None else None
    chosen = [
        r for r in view.rules
        if r.test and r.test.strength_blocked is None
        and (r.id in wanted if wanted is not None else r.test.strength_status == "pendiente")
    ]
    if not chosen:
        raise ApiError(409, "nothing_to_test", "No hay pruebas que pasen sin prueba de fuerza; elige cuáles volver a medir")
    reason = await asyncio.to_thread(sandbox._available, settings)
    if reason:
        raise ApiError(409, "sandbox_unavailable", f"No se puede usar el sandbox: {reason}")
    mp = await asyncio.to_thread(mapa.build, ctx.ws.root, ctx.ws.list_files([]))
    by_id = {r.id: r for r in ctx.rules}
    evidences = EvidenceStore(store.conn).all(project_id)
    plan: Plan = {}
    left = fuerza.MAX_TOTAL
    for r in chosen:
        ev = evidencia.loads(evidences[r.id]["data"]) if r.evidence and not r.evidence.stale else None
        ms, found = await asyncio.to_thread(fuerza.mutants, ctx.ws.root, mp, by_id[r.id], r.test.endpoints, ev, max(0, min(fuerza.MAX_MUTANTS, left)), list(by_id.values()))
        left -= len(ms)
        plan[r.id] = (ms, found)
    hashes = {r.id: arnes.code_hash(r.test.code) for r in chosen if r.test}
    objectives = [(r.id, r.test.file, plan[r.id][0]) for r in chosen if r.test and plan[r.id][0]]
    ts = RuleTestsStore(store.conn)
    ts.strength_running(project_id, hashes)
    if not objectives:
        # Nada que mutar: se sabe sin el sandbox
        results = fuerza.read({"objetivos": []}, {"venv": (0, ""), "install": (0, ""), "tests": (0, "")}, plan)
        ts.save_strength(project_id, {rid: (hashes[rid], results[rid].to_dict()) for rid in hashes})
        return _view(store.conn, settings, project_id)
    files = {r.test.file: r.test.code for r in chosen if r.test and plan[r.id][0]}
    overlay = {**pruebas.overlay(ctx.harness, files), fuerza.SPEC: json.dumps(fuerza.spec(objectives), ensure_ascii=False)}
    _busy[project_id] = Busy("fuerza", len(objectives))
    _busy[project_id].task = asyncio.create_task(_strength(settings, project_id, overlay, hashes, plan))
    return _view(store.conn, settings, project_id)
