"""Editor de código y correcciones automáticas (docs/FRONTEND_SPEC.md §5.8 y §6.5)."""

import sqlite3
from collections import defaultdict
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.analyses.access import Analyses, UserId, require_repo
from app.analyses.analyzers import (
    AnalyzerError,
    diff_patches,
    fix_content,
    static_findings,
)
from app.analyses.models import FindingInput
from app.analyses.store import AnalysisStore
from app.analyses.views import SEV_ORDER, report_scores, visible
from app.analyses.workspace import Workspace, language_of, snippet
from app.config import Settings, get_settings
from app.errors import ApiError

router = APIRouter(prefix="/api", tags=["editor"])

# Herramientas cuyo resultado se puede recalcular al guardar un archivo
REANALYZED_TOOLS = {"Ruff", "Bandit"}
MAX_FIX_FINDINGS = 50

Config = Annotated[Settings, Depends(get_settings)]


class TreeEntry(BaseModel):
    path: str
    dir: str
    open_findings: int
    worst: Literal["alta", "media", "baja"] | None


class FileResponse(BaseModel):
    path: str
    language: str
    content: str


class SaveFileRequest(BaseModel):
    repo_id: str = Field(max_length=64)
    path: str = Field(max_length=500)
    content: str


class SaveFileResponse(BaseModel):
    resolved_ids: list[int]
    # Hallazgos que aparecieron con el cambio (ya forman parte del último reporte)
    new_ids: list[int]
    score_before: float
    score_after: float


class FixRequest(BaseModel):
    repo_id: str = Field(max_length=64)
    finding_ids: list[int] = Field(min_length=1, max_length=MAX_FIX_FINDINGS)


class Patch(BaseModel):
    file: str
    line: int
    original: str
    text: str | None


class FixResponse(BaseModel):
    patches: list[Patch]


def workspace(settings: Settings, repo_id: str) -> Workspace:
    ws = Workspace(settings, repo_id)
    if not ws.exists():
        raise ApiError(404, "not_cloned", "Este repositorio aún no se ha clonado. Vuelve a analizarlo.")
    return ws


def analyzer_failure(exc: AnalyzerError) -> ApiError:
    return ApiError(502, "analyzer_failed", f"No se pudo analizar el archivo: {exc}")


@router.get("/repos/{repo_id}/tree", response_model=list[TreeEntry])
def tree(repo_id: str, store: Analyses, user_id: UserId, settings: Config) -> list[TreeEntry]:
    require_repo(store, user_id, repo_id)
    cfg = store.config(repo_id)
    latest = store.latest_report(repo_id)
    by_file: dict[str, list[str]] = defaultdict(list)
    if latest:
        for f in visible(store.findings(latest["id"]), cfg):
            if f["status"] == "open":
                by_file[f["file"]].append(f["sev"])
    entries = []
    for path in workspace(settings, repo_id).list_files(cfg.excluded):
        sevs = by_file.get(path, [])
        entries.append(TreeEntry(path=path, dir=path.rsplit("/", 1)[0] if "/" in path else "", open_findings=len(sevs), worst=min(sevs, key=SEV_ORDER.get) if sevs else None))
    # Agrupado por carpeta (el árbol del frontend pinta un encabezado al cambiar de carpeta)
    return sorted(entries, key=lambda e: (e.dir, e.path))


@router.get("/file", response_model=FileResponse)
def read_file(store: Analyses, user_id: UserId, settings: Config, repo: str = Query(max_length=64), path: str = Query(max_length=500)) -> FileResponse:
    require_repo(store, user_id, repo)
    return FileResponse(path=path, language=language_of(path), content=workspace(settings, repo).read(path))


def _match(existing: sqlite3.Row, current: list[FindingInput], lines: list[str]) -> FindingInput | None:
    """El resultado actual que corresponde a un hallazgo previo: misma regla y mismo texto de línea (el más cercano)."""
    candidates = [
        f for f in current
        if f.rule == existing["rule"] and (not existing["code"] or (f.line <= len(lines) and lines[f.line - 1].rstrip("\r") == existing["code"]))
    ]
    return min(candidates, key=lambda f: abs(f.line - existing["line"]), default=None)


def reanalyze_file(store: AnalysisStore, ws: Workspace, report_id: str, path: str, content: str) -> tuple[list[int], list[int]]:
    """Recalcula Ruff y Bandit del archivo: resuelve lo que ya no aparece y agrega lo nuevo."""
    try:
        current = static_findings(content, path, ws.root)
    except AnalyzerError as exc:
        raise analyzer_failure(exc) from exc
    lines = content.split("\n")
    resolved = []
    for f in store.findings(report_id, file=path):
        if f["status"] != "open" or f["tool"] not in REANALYZED_TOOLS:
            continue
        match = _match(f, current, lines)
        if match is None:
            resolved.append(f["id"])
            continue
        current.remove(match)
        if match.line != f["line"]:
            store.move_finding(f["id"], match.line, snippet(lines, match.line))
    store.resolve_findings(resolved)
    new_ids = store.add_findings(report_id, current, lines_by_file={path: lines})
    return resolved, new_ids


@router.put("/file", response_model=SaveFileResponse)
def save_file(body: SaveFileRequest, store: Analyses, user_id: UserId, settings: Config) -> SaveFileResponse:
    """Guarda (con respaldo) y re-analiza el archivo; devuelve el efecto en el score del último reporte."""
    require_repo(store, user_id, body.repo_id)
    ws = workspace(settings, body.repo_id)
    latest = store.latest_report(body.repo_id)
    cfg = store.config(body.repo_id)
    before = report_scores(store, latest, cfg).global_ if latest else 0.0
    ws.write(body.path, body.content)
    if latest is None or not body.path.endswith(".py"):
        return SaveFileResponse(resolved_ids=[], new_ids=[], score_before=before, score_after=before)
    resolved, new_ids = reanalyze_file(store, ws, latest["id"], body.path, body.content)
    after = report_scores(store, latest, cfg).global_
    return SaveFileResponse(resolved_ids=resolved, new_ids=new_ids, score_before=before, score_after=after)


@router.post("/fix", response_model=FixResponse)
def fix(body: FixRequest, store: Analyses, user_id: UserId, settings: Config) -> FixResponse:
    """Parches de las correcciones automáticas, calculados sobre la versión guardada de cada archivo."""
    require_repo(store, user_id, body.repo_id)
    latest = store.latest_report(body.repo_id)
    rows = store.findings_by_id(body.finding_ids)
    if latest is None or len(rows) != len(set(body.finding_ids)) or any(r["report_id"] != latest["id"] for r in rows):
        raise ApiError(404, "not_found", "Hallazgo no encontrado en el último análisis")
    fixable = [r for r in rows if r["fix"] and r["status"] == "open"]
    if not fixable:
        raise ApiError(422, "fix_unavailable", "Estos hallazgos no tienen corrección automática")
    ws = workspace(settings, body.repo_id)
    by_file: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
    for r in fixable:
        by_file[r["file"]].append((r["rule"], r["code"], r["line"]))
    patches = []
    for path, targets in by_file.items():
        content = ws.read(path)
        try:
            fixed = fix_content(content, path, ws.root, targets)
        except AnalyzerError as exc:
            raise analyzer_failure(exc) from exc
        patches += diff_patches(path, content, fixed)
    return FixResponse(patches=[Patch(**p) for p in patches])
