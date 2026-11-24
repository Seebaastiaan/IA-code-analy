"""
«Preparar todo» en el servidor (docs/PLAN_REGLAS_AUTOMATICO.md, pasos 1 y 2).

Encadena lo que antes eran siete botones: aprobar las reglas sin dudas → arnés → prueba de humo → escribir las pruebas →
correrlas → prueba de fuerza → segunda opinión (la IA lee el código sin ver la prueba). Llama a las mismas funciones de
las rutas de siempre, así que valen sus mismas validaciones, y se detiene en el primer problema diciendo qué hacer.

Corre como tarea del servidor: sigue aunque se cierre la pestaña y cualquiera del equipo ve su avance.

- `POST   /api/projects/{id}/reglas/preparar`: lo lanza (409 si ya está corriendo). Responde enseguida.
- `GET    /api/projects/{id}/reglas/preparar`: estado de cada paso y resumen del último.
- `DELETE /api/projects/{id}/reglas/preparar`: lo detiene al terminar el paso en curso.
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app import db
from app.analyses.access import Analyses, UserId, require_repo
from app.analyses.store import AnalysisStore
from app.analysis.router import Config
from app.assistant.llm import LLM
from app.config import Settings
from app.errors import ApiError
from app.projects import arnes as harness_routes
from app.projects import pruebas as test_routes
from app.projects import reglas as rule_routes

log = logging.getLogger(__name__)
router = APIRouter(tags=["reglas de negocio"])

StepId = Literal["reglas", "arnes", "humo", "pruebas", "correr", "fuerza", "revision"]
Status = Literal["pendiente", "haciendo", "hecho", "fallo"]

STEPS: list[tuple[StepId, str]] = [
    ("reglas", "Aprobar las reglas que no tienen dudas"),
    ("arnes", "Preparar el entorno de pruebas del proyecto"),
    ("humo", "Comprobar que el proyecto arranca"),
    ("pruebas", "Escribir una prueba para cada regla"),
    ("correr", "Ejecutar las pruebas"),
    ("fuerza", "Verificar que las pruebas sí detectan una regla rota"),
    ("revision", "Segunda opinión: la IA lee el código por su cuenta y se compara"),
]

POLL_SECONDS = 2.0
# Un paso lento (instalar dependencias, correr pruebas) no debe colgar el flujo para siempre
MAX_WAIT_SECONDS = 15 * 60
STOPPED = "Detenido"
DONE = "Listo. El siguiente análisis usará estas reglas y pruebas."


@dataclass
class Step:
    id: StepId
    label: str
    status: Status = "pendiente"
    note: str | None = None


@dataclass
class Job:
    user_id: str
    steps: list[Step] = field(default_factory=lambda: [Step(i, label) for i, label in STEPS])
    running: bool = True
    summary: str | None = None
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    finished_at: str | None = None
    cancelled: bool = False
    task: asyncio.Task | None = field(default=None, repr=False)
    # Dónde se guarda (para verlo después de reiniciar el servidor); None = solo en memoria
    path: Path | None = field(default=None, repr=False)

    def patch(self, step: StepId, status: Status, note: str | None = None) -> None:
        for s in self.steps:
            if s.id == step:
                s.status, s.note = status, note
        self.save()

    def save(self) -> None:
        if self.path is None:
            return
        data = {
            "user_id": self.user_id, "steps": [vars(s) for s in self.steps], "running": self.running, "summary": self.summary,
            "started_at": self.started_at, "finished_at": self.finished_at,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except OSError:
            log.warning("No se pudo guardar el avance de «Preparar todo» en %s", self.path, exc_info=True)


INTERRUPTED = "Se interrumpió porque el servidor se reinició: pulsa «Reintentar» (lo ya hecho se conserva)"


def _path(settings: Settings, repo_id: str) -> Path:
    return Path(settings.database_path).resolve().parent / "preparar" / f"{repo_id}.json"


def _saved(settings: Settings, repo_id: str) -> Job | None:
    """
    El último «Preparar todo» guardado. Si el servidor se reinició a mitad, la tarea ya no existe: el paso en curso queda
    como interrumpido (antes la tarjeta volvía a estar vacía, como si no se hubiera hecho nada).
    """
    path = _path(settings, repo_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    try:
        job = Job(
            user_id=data["user_id"], steps=[Step(**st) for st in data["steps"]], running=False, summary=data.get("summary"),
            started_at=data["started_at"], finished_at=data.get("finished_at"), path=path,
        )
    except (KeyError, TypeError):
        return None
    if data.get("running"):
        for st in job.steps:
            if st.status == "haciendo":
                st.status, st.note = "fallo", INTERRUPTED
        job.finished_at = job.finished_at or datetime.now(UTC).isoformat(timespec="seconds")
        job.save()
    return job


def _current(settings: Settings, repo_id: str) -> Job | None:
    job = _jobs.get(repo_id)
    if job is None:
        job = _saved(settings, repo_id)
        if job is not None:
            _jobs[repo_id] = job
    return job


# El último «Preparar todo» de cada repo (el que corre o el que terminó): se ve al volver a la pantalla
_jobs: dict[str, Job] = {}


class Stop(Exception):
    """El flujo se detiene a propósito: un paso no pudo seguir o el equipo pulsó Detener."""


# ───────────────────────── Modelos de la API ─────────────────────────


class StepOut(BaseModel):
    id: StepId
    label: str
    status: Status
    note: str | None


class PrepareView(BaseModel):
    running: bool
    steps: list[StepOut]
    summary: str | None
    started_at: str | None
    finished_at: str | None


def _out(job: Job | None) -> PrepareView:
    if job is None:
        return PrepareView(running=False, steps=[StepOut(id=i, label=label, status="pendiente", note=None) for i, label in STEPS], summary=None, started_at=None, finished_at=None)
    return PrepareView(
        running=job.running, steps=[StepOut(**vars(s)) for s in job.steps], summary=job.summary, started_at=job.started_at, finished_at=job.finished_at,
    )


# ───────────────────────── El flujo ─────────────────────────


class Flow:
    """Un «Preparar todo»: cada paso abre su propia conexión corta (como los demás trabajos en segundo plano)."""

    def __init__(self, settings: Settings, repo_id: str, job: Job, llm: LLM | None):
        self.settings, self.repo_id, self.job, self.llm = settings, repo_id, job, llm
        # Reglas cuya lectura del código falló (la IA no respondió): se siguen las demás
        self.unread: list[str] = []

    async def explain(self, rule_id: str) -> int:
        """
        La segunda opinión de una regla. Si la IA no responde (tiempo agotado, saturada), se anota y se sigue con las
        demás: antes un solo «ReadTimeout» detenía el paso y no se aprobaba nada. 1 si se leyó, 0 si no.
        """
        uid, rid, cfg, llm = self.job.user_id, self.repo_id, self.settings, self.llm
        try:
            await self.call(lambda s: test_routes.explain_rule(rid, rule_id, s, uid, cfg, llm))
        except ApiError as exc:
            if exc.status != 503:
                raise
            if rule_id not in self.unread:
                self.unread.append(rule_id)
            return 0
        if rule_id in self.unread:
            self.unread.remove(rule_id)
        return 1

    def check(self) -> None:
        if self.job.cancelled:
            raise Stop(STOPPED)

    def fail(self, step: StepId, note: str) -> None:
        self.job.patch(step, "fallo", note)
        raise Stop(note)

    async def call[T](self, fn: Callable[[AnalysisStore], T | Awaitable[T]]) -> T:
        with db.session(self.settings.database_path) as conn:
            out = fn(AnalysisStore(conn))
            if asyncio.iscoroutine(out):
                out = await out
            return out  # type: ignore[return-value]

    async def until(self, busy: Callable[[], bool]) -> None:
        """Espera a que termine un trabajo en segundo plano del servidor (prueba de humo, generar, correr, fuerza)."""
        waited = 0.0
        while busy():
            self.check()
            if waited > MAX_WAIT_SECONDS:
                raise Stop("Tardó demasiado: inténtalo de nuevo")
            await asyncio.sleep(POLL_SECONDS)
            waited += POLL_SECONDS

    async def smoke(self) -> harness_routes.HarnessView:
        """Corre la prueba de humo del arnés actual y espera su resultado."""
        uid, rid, cfg = self.job.user_id, self.repo_id, self.settings
        await self.call(lambda s: harness_routes.run_smoke(rid, s, uid, cfg))
        await self.until(lambda: rid in harness_routes._running)
        return await self.harness()

    def tests(self) -> Awaitable[test_routes.TestsView]:
        return self.call(lambda s: test_routes.list_tests(self.repo_id, s, self.job.user_id, self.settings))

    def harness(self) -> Awaitable[harness_routes.HarnessView]:
        return self.call(lambda s: harness_routes.get_harness(self.repo_id, s, self.job.user_id, self.settings))

    async def run(self) -> None:
        uid, rid, cfg = self.job.user_id, self.repo_id, self.settings

        # 1 · Reglas: las que no tienen dudas se aprueban solas (las demás esperan una decisión del equipo)
        self.job.patch("reglas", "haciendo")
        project = await self.call(lambda s: rule_routes.get_rules(rid, s, uid, cfg))
        source = project.repo if project.active == "repo" else project.uploaded
        rules = source.rules if source and source.valid else []
        if not rules:
            self.fail("reglas", "Todavía no hay reglas: sube el documento de requisitos o escribe una regla.")
        ready = [r.id for r in rules if r.status == "borrador" and not r.doubts]
        if ready:
            body = rule_routes.RuleStates(ids=ready, status="aprobada", by="programa")
            project = await self.call(lambda s: rule_routes.set_states(rid, body, s, uid, cfg))
        current = project.repo if project.active == "repo" else project.uploaded
        everything = current.rules if current else []
        approved = [r for r in everything if r.status == "aprobada"]
        if not approved:
            self.fail("reglas", "Todas las reglas tienen dudas: respóndelas y vuelve a intentar.")
        waiting = len(everything) - len(approved)
        self.job.patch("reglas", "hecho", f"{len(approved)} aprobadas · {waiting} esperan tu decisión (tienen dudas)" if waiting else f"{len(approved)} aprobadas")
        self.check()

        # 2 · Entorno de pruebas (arnés): el del repo si ya existe; si no, la IA lo propone
        self.job.patch("arnes", "haciendo")
        view = await self.harness()
        if not view.cloned:
            self.fail("arnes", "Analiza el repositorio una vez para poder preparar sus pruebas.")
        if view.harness is None:
            if view.repo_harness:
                view = await self.call(lambda s: harness_routes.use_repo_harness(rid, s, uid, cfg))
            elif view.can_generate and self.llm is not None:
                llm = self.llm
                view = await self.call(lambda s: harness_routes.create_harness(rid, s, uid, cfg, llm))
            else:
                self.fail("arnes", "No se pudo preparar: falta configurar la clave de la IA o el repositorio no usa FastAPI, Flask ni Django.")
        origin = view.harness.origin if view.harness else None
        self.job.patch("arnes", "hecho", "Usé el conftest.py de tu repositorio" if origin == "repo" else "La IA lo preparó con el mapa de tu proyecto")
        self.check()

        # 3 · Prueba de humo y aprobación del entorno
        self.job.patch("humo", "haciendo")
        if not view.sandbox:
            self.fail("humo", "Falta el sandbox: configura SANDBOX=docker o wsl para poder correr pruebas.")
        if view.harness is None or view.harness.smoke != "paso":
            view = await self.smoke()
        # El arnés de la IA no arrancó: se le da el error y se prueba una vez más (con repos ajenos pasa a menudo)
        fixed_harness = False
        if view.harness is not None and view.harness.smoke == "fallo" and view.harness.origin == "ia" and view.can_generate and self.llm is not None:
            self.check()
            llm = self.llm
            await self.call(lambda s: harness_routes.create_harness(rid, s, uid, cfg, llm))
            view = await self.smoke()
            fixed_harness = view.harness is not None and view.harness.smoke == "paso"
        if view.harness is None or view.harness.smoke != "paso":
            self.fail("humo", (view.harness.smoke_message if view.harness else None) or "El entorno no arrancó: revisa el arnés en «Avanzado».")
        if not view.harness.approved:
            await self.call(lambda s: harness_routes.approve_harness(rid, s, uid, cfg))
        self.job.patch("humo", "hecho", "El entorno arranca y se aprobó" + (" (la IA corrigió el entorno tras un primer intento que no arrancó)" if fixed_harness else ""))
        self.check()

        # 4 · Una prueba por regla aprobada (las que ya tienen una vigente se conservan)
        self.job.patch("pruebas", "haciendo")
        t = await self.tests()
        # Sin prueba, de una versión anterior de la regla o que usa rutas que el código ya no tiene
        missing = [r.id for r in t.rules if r.test is None or r.test.outdated or r.test.gone_endpoints]
        if missing:
            if not t.can_generate or self.llm is None:
                self.fail("pruebas", "Escribir las pruebas usa la IA: configura GEMINI_API_KEY.")
            llm = self.llm
            await self.call(lambda s: test_routes.generate_tests(rid, test_routes.Ids(ids=missing), s, uid, cfg, llm))
            await self.until(lambda: rid in test_routes._busy)
            t = await self.tests()
        written = sum(1 for r in t.rules if r.test)
        if not written:
            self.fail("pruebas", t.messages[0] if t.messages else "La IA no pudo escribir pruebas: reintenta en unos minutos.")
        self.job.patch("pruebas", "hecho", f"{written} pruebas escritas" + (f" · {t.messages[0]}" if t.messages else ""))
        self.check()

        # 5 · Corrida en el sandbox (solo las que no han corrido con su código actual)
        self.job.patch("correr", "haciendo")
        if any(r.test and r.test.kind == "prueba" and not r.test.errors and not r.test.outdated and r.test.run_status == "pendiente" for r in t.rules):
            await self.call(lambda s: test_routes.run_tests(rid, test_routes.Ids(), s, uid, cfg))
            await self.until(lambda: rid in test_routes._busy)
            t = await self.tests()
        verdicts = [r.test.run.verdict for r in t.rules if r.test and r.test.run]
        self.job.patch("correr", "hecho", f"{verdicts.count('cumple')} cumplen · {verdicts.count('no_cumple')} no cumplen · {verdicts.count('prueba_rota')} con prueba rota")
        self.check()

        # 6 · Prueba de fuerza: ¿la prueba detecta una violación de la regla?
        self.job.patch("fuerza", "haciendo")
        if any(r.test and r.test.strength_status == "pendiente" and not r.test.strength_blocked for r in t.rules):
            try:
                await self.call(lambda s: test_routes.strength_tests(rid, test_routes.Ids(), s, uid, cfg))
            except ApiError as exc:
                if exc.code != "nothing_to_test":
                    raise
            await self.until(lambda: rid in test_routes._busy)
            t = await self.tests()
        weak = sum(1 for r in t.rules if r.test and r.test.strength and r.test.strength.status not in ("fuerte", "no_aplica"))
        self.job.patch("fuerza", "hecho", f"{weak} pruebas flojas para revisar" if weak else "Todas detectan las violaciones")
        self.check()

        # 7 · Segunda opinión: la IA lee el código sin ver la prueba y se compara con el resultado de la corrida
        self.job.patch("revision", "haciendo")
        read = 0
        if t.can_explain and self.llm is not None:
            for row in t.rules:
                self.check()
                verdict = row.test.run.verdict if row.test and row.test.run else None
                if verdict in ("cumple", "no_cumple") and (row.evidence is None or row.evidence.stale):
                    read += await self.explain(row.id)
            t = await self.tests()
        # Si la prueba y la lectura no coinciden, una de las dos se equivocó. La IA no escribe igual cada vez, así que la
        # prueba se escribe una vez más (solo las de la IA que nadie aprobó), se corre y se mide; la lectura se conserva
        # Las que se rompieron al preparar el escenario también: la IA la corrige con el error a la vista
        broken = {r.id for r in t.rules if r.test and r.test.run is not None and r.test.run.verdict == "prueba_rota"}
        # Y las flojas: pasan, pero también pasaron con el código cambiado a propósito (así se escapaban reglas rotas); la IA
        # la reescribe viendo esos cambios
        weak = {r.id for r in t.rules if is_weak(r)}
        retry = [
            r.id for r in t.rules
            if r.test and r.test.origin == "ia" and not r.test.approved and (r.crosscheck.status == "discrepa" or r.id in broken or r.id in weak)
        ]
        if retry and t.can_generate and self.llm is not None:
            t = await self.second_try(retry)
            # Una prueba que estaba rota no tenía lectura del código: ahora que da un resultado, se lee
            pending = [
                r.id for r in t.rules
                if r.id in retry and r.test and r.test.run and r.test.run.verdict in ("cumple", "no_cumple") and (r.evidence is None or r.evidence.stale)
            ]
            for rule_id in pending:
                self.check()
                read += await self.explain(rule_id)
            if pending:
                t = await self.tests()
        trusted = [r.id for r in t.rules if trusted_by_program(r)]
        if trusted:
            await self.call(lambda s: test_routes.approve_tests(rid, test_routes.Ids(ids=trusted), s, uid, cfg))
        # En palabras: cuántas aprobó solo y cuántas esperan a una persona (el detalle técnico queda en la tabla de pruebas)
        waiting = sum(1 for r in t.rules if r.test and r.test.kind == "prueba" and not r.test.approved and r.id not in trusted)
        note = f"{len(trusted)} aprobadas solas"
        if waiting:
            note += f" · {waiting} esperan tu revisión (pruebas que no pasaron todos los controles)"
        if self.unread:
            note += f" · {len(self.unread)} sin leer porque la IA no respondió: reintenta en un rato"
        if not t.can_explain or self.llm is None:
            note += " · sin IA para leer el código: nada se aprueba solo"
        self.job.patch("revision", "hecho", note)
        self.job.summary = DONE

    async def second_try(self, ids: list[str]) -> test_routes.TestsView:
        """Escribe de nuevo, corre y mide la fuerza de las pruebas de `ids` (una sola vez por «Preparar todo»)."""
        uid, rid, cfg, llm = self.job.user_id, self.repo_id, self.settings, self.llm
        assert llm is not None
        await self.call(lambda s: test_routes.generate_tests(rid, test_routes.Ids(ids=ids), s, uid, cfg, llm))
        await self.until(lambda: rid in test_routes._busy)
        self.check()
        t = await self.tests()
        runnable = [r.id for r in t.rules if r.id in ids and r.test and r.test.kind == "prueba" and not r.test.errors and not r.test.outdated]
        if not runnable:
            return t
        await self.call(lambda s: test_routes.run_tests(rid, test_routes.Ids(ids=runnable), s, uid, cfg))
        await self.until(lambda: rid in test_routes._busy)
        self.check()
        t = await self.tests()
        strong = [r.id for r in t.rules if r.id in runnable and r.test and not r.test.strength_blocked]
        if strong:
            await self.call(lambda s: test_routes.strength_tests(rid, test_routes.Ids(ids=strong), s, uid, cfg))
            await self.until(lambda: rid in test_routes._busy)
            t = await self.tests()
        return t


def is_weak(row) -> bool:
    """Una prueba que pasa y que la prueba de fuerza dejó parcial o débil (no notó algún cambio a las líneas de la regla)."""
    t = row.test
    return (
        t is not None and t.run is not None and t.run.verdict == "cumple"
        and t.strength is not None and t.strength.status in ("parcial", "debil")
    )


def trusted_by_program(row) -> bool:
    """
    Se aprueba sola una prueba que nadie aprobó cuando dos comprobaciones que no se ven entre sí dicen lo mismo:
    - pasa, es fuerte (notó todas las violaciones inyectadas) y la lectura del código confirma la regla; o
    - falla y la lectura del código tampoco encuentra la regla completa. La prueba de fuerza no aplica aquí: mide si una
      prueba que pasa es floja, y una que falla ya está señalando el problema.
    Una que falla NO se aprueba sola si el repo trae sus propias pruebas de esa regla: con f1-pitwall dos reglas se
    aprobaron solas como «no cumple» (la lectura «no encontró» el código porque no le llegaron los fragmentos) mientras
    las pruebas del autor de esas mismas reglas pasaban.
    """
    t = row.test
    if t is None or t.approved or t.blocked or row.crosscheck.status != "coincide" or t.run is None:
        return False
    if t.run.verdict == "cumple":
        return t.strength is not None and t.strength.status == "fuerte"
    return t.run.verdict == "no_cumple" and not getattr(row, "repo_tests", 0)


async def _work(flow: Flow) -> None:
    job = flow.job
    try:
        await flow.run()
    except Stop as exc:
        if str(exc) == STOPPED:
            for s in job.steps:
                if s.status == "haciendo":
                    s.status, s.note = "pendiente", STOPPED
        else:
            # Un paso que no se marcó (p. ej. «Tardó demasiado») queda como falla con el motivo
            for s in job.steps:
                if s.status == "haciendo":
                    s.status, s.note = "fallo", str(exc)
    except ApiError as exc:
        # La misma validación que verían los botones (409, 422, 503…): se muestra en el paso que estaba corriendo
        for s in job.steps:
            if s.status == "haciendo":
                s.status, s.note = "fallo", exc.message
    except Exception as exc:  # cualquier falla se le muestra al equipo, no se pierde
        log.exception("Preparar todo de %s", flow.repo_id)
        for s in job.steps:
            if s.status == "haciendo":
                s.status, s.note = "fallo", f"Algo falló: {exc}"
    finally:
        job.running = False
        job.finished_at = datetime.now(UTC).isoformat(timespec="seconds")
        job.save()


# ───────────────────────── Rutas ─────────────────────────


def get_optional_llm(settings: Config) -> LLM | None:
    """La IA si hay clave; sin ella el flujo corre igual y se detiene en el primer paso que la necesite."""
    return LLM(settings) if settings.gemini_api_key else None


@router.get("/api/projects/{project_id}/reglas/preparar", response_model=PrepareView)
def get_prepare(project_id: str, store: Analyses, user_id: UserId, settings: Config) -> PrepareView:
    require_repo(store, user_id, project_id)
    return _out(_current(settings, project_id))


@router.post("/api/projects/{project_id}/reglas/preparar", response_model=PrepareView)
async def start_prepare(
    project_id: str, store: Analyses, user_id: UserId, settings: Config, llm: Annotated[LLM | None, Depends(get_optional_llm)],
) -> PrepareView:
    """Lanza «Preparar todo» en segundo plano. Sin clave de IA corre igual y se detiene donde la necesite."""
    require_repo(store, user_id, project_id)
    current = _current(settings, project_id)
    if current is not None and current.running:
        raise ApiError(409, "prepare_running", "«Preparar todo» ya está corriendo en este proyecto")
    job = Job(user_id=user_id, path=_path(settings, project_id))
    job.save()
    _jobs[project_id] = job
    job.task = asyncio.create_task(_work(Flow(settings, project_id, job, llm)))
    return _out(job)


@router.delete("/api/projects/{project_id}/reglas/preparar", response_model=PrepareView)
def stop_prepare(project_id: str, store: Analyses, user_id: UserId, settings: Config) -> PrepareView:
    """Detiene «Preparar todo» al terminar el paso en curso (lo que ya corre en el sandbox termina por su cuenta)."""
    require_repo(store, user_id, project_id)
    job = _current(settings, project_id)
    if job is not None and job.running:
        job.cancelled = True
    return _out(job)
