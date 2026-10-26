"""
Comparativa entre dos análisis del mismo repo (docs/FRONTEND_SPEC.md §5.10 y §6.7):
GET /api/repos/{id}/analyses (opciones de los selectores A/B) y POST /api/diff.

Cada análisis guarda sus hallazgos con ids nuevos, así que un mismo problema no conserva su id entre
reportes. Se reconoce por su huella: herramienta, regla, archivo y texto de la línea señalada (no el
número de línea, que cambia en cuanto se edita algo arriba).
"""

import sqlite3
from collections import Counter
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.analyses.access import Analyses, UserId, require_repo
from app.analyses.schemas import Finding, Scores
from app.analyses.store import AnalysisStore
from app.analyses.views import finding_view, scores, visible
from app.errors import ApiError

router = APIRouter(prefix="/api", tags=["comparativa"])

MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
MAX_OPTIONS = 100


class AnalysisOption(BaseModel):
    id: str
    label: str


class DiffRequest(BaseModel):
    base: str = Field(min_length=1, max_length=100)
    target: str = Field(min_length=1, max_length=100)


class DiffResponse(BaseModel):
    a: Scores
    b: Scores
    new: list[Finding]
    resolved: list[Finding]


def _fecha(iso: str) -> str:
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return iso[:10]
    return f"{d.day:02d} {MESES[d.month - 1]}"


def label(report: sqlite3.Row) -> str:
    """Ej. "#4 · 17 oct · main". La rama va en la etiqueta: así también se comparan ramas entre sí."""
    return f"#{report['num']} · {_fecha(report['created_at'])} · {report['branch']}"


def fingerprint(row: sqlite3.Row) -> tuple[str, str, str, str]:
    return (row["tool"], row["rule"], row["file"], (row["code"] or "").strip())


def unmatched(rows: list[sqlite3.Row], other: list[sqlite3.Row]) -> list[sqlite3.Row]:
    """Hallazgos de `rows` sin pareja en `other`. Cuenta repetidos: 3 iguales contra 1 deja 2 sin pareja."""
    pool = Counter(fingerprint(r) for r in other)
    out = []
    for r in rows:
        key = fingerprint(r)
        if pool[key]:
            pool[key] -= 1
        else:
            out.append(r)
    return out


def _own_report(store: AnalysisStore, user_id: str, report_id: str) -> sqlite3.Row:
    """El reporte si su repo es del usuario; 404 en cualquier otro caso para no revelar que existe."""
    report = store.report(report_id.strip())
    if report is None:
        raise ApiError(404, "not_found", "Análisis no encontrado")
    try:
        require_repo(store, user_id, report["repo_id"])
    except ApiError as exc:
        raise ApiError(404, "not_found", "Análisis no encontrado") from exc
    return report


@router.get("/repos/{repo_id}/analyses", response_model=list[AnalysisOption])
def analyses(repo_id: str, store: Analyses, user_id: UserId) -> list[AnalysisOption]:
    """Análisis del repo, del más reciente al más antiguo (el frontend compara por defecto [1] contra [0])."""
    require_repo(store, user_id, repo_id)
    rows = store.recent_reports(repo_id, MAX_OPTIONS)[::-1]
    return [AnalysisOption(id=r["id"], label=label(r)) for r in rows]


@router.post("/diff", response_model=DiffResponse)
def diff(body: DiffRequest, store: Analyses, user_id: UserId) -> DiffResponse:
    a = _own_report(store, user_id, body.base)
    b = _own_report(store, user_id, body.target)
    if a["repo_id"] != b["repo_id"]:
        raise ApiError(422, "different_repos", "Solo se pueden comparar análisis del mismo repositorio")

    # La configuración actual (reglas ignoradas, rutas excluidas, pesos) se aplica a los dos lados por igual
    cfg = store.config(a["repo_id"])
    rows_a, rows_b = visible(store.findings(a["id"]), cfg), visible(store.findings(b["id"]), cfg)
    open_a = [f for f in rows_a if f["status"] == "open"]
    open_b = [f for f in rows_b if f["status"] == "open"]

    return DiffResponse(
        a=scores(a, rows_a, cfg),
        b=scores(b, rows_b, cfg),
        # "Nuevos" llevan ids de B: el frontend abre el reporte B con ese hallazgo
        new=[finding_view(f, with_code=False) for f in unmatched(open_b, open_a)],
        resolved=[finding_view(f, with_code=False).model_copy(update={"status": "resolved"}) for f in unmatched(open_a, open_b)],
    )
