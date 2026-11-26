"""Tablero y lista de repositorios (docs/FRONTEND_SPEC.md §5.2, §5.4 y §6.2)."""

import logging

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel

from app.analyses.access import Analyses, Jobs, UserId, require_repo
from app.analyses.schemas import Finding, Repo, Scores, Thresholds
from app.analyses.store import AnalysisStore
from app.analyses.views import finding_view, repo_view, report_scores, scores, visible
from app.analyses.workspace import Workspace
from app.analysis.clone import remove_tree
from app.analysis.router import Config
from app.errors import ApiError
from app.teams.store import delete_repo, membership, remove_repo_clones

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["tablero"])

HISTORY_POINTS = 7
TOP_FINDINGS = 4


class HistoryPoint(Scores):
    date: str


class DashboardSelected(BaseModel):
    repo: Repo
    report_id: str
    num: int
    scores: Scores
    prev_scores: Scores | None
    history: list[HistoryPoint]
    top_findings: list[Finding]
    open_findings: int


class DashboardResponse(BaseModel):
    active_repos: int
    repos: list[Repo]
    thresholds: Thresholds
    selected: DashboardSelected | None


def history(store: AnalysisStore, repo_id: str, limit: int) -> list[HistoryPoint]:
    cfg = store.config(repo_id)
    return [
        HistoryPoint(date=r["created_at"], **report_scores(store, r, cfg).model_dump(by_alias=False))
        for r in store.recent_reports(repo_id, limit)
    ]


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(store: Analyses, user_id: UserId, jobs: Jobs, repo: str | None = Query(default=None, max_length=64)) -> DashboardResponse:
    repos = [repo_view(store, jobs, r) for r in store.repos(user_id)]
    ready = [r for r in repos if r.last_report_id]
    # El repo pedido si es del usuario y tiene reporte; si no, el primero con reporte
    chosen = next((r for r in ready if r.id == repo), ready[0] if ready else None)
    thresholds = Thresholds(**store.config(chosen.id).thresholds) if chosen else Thresholds(score=70, cov=60)
    if chosen is None:
        return DashboardResponse(active_repos=0, repos=repos, thresholds=thresholds, selected=None)

    cfg = store.config(chosen.id)
    latest = store.report(chosen.last_report_id)
    rows = visible(store.findings(latest["id"]), cfg)
    open_rows = [f for f in rows if f["status"] == "open"]
    prev = store.previous_report(chosen.id, latest["num"])
    return DashboardResponse(
        active_repos=len(ready),
        repos=repos,
        thresholds=thresholds,
        selected=DashboardSelected(
            repo=chosen,
            report_id=latest["id"],
            num=latest["num"],
            scores=scores(latest, rows, cfg),
            prev_scores=report_scores(store, prev, cfg) if prev else None,
            history=history(store, chosen.id, HISTORY_POINTS),
            top_findings=[finding_view(f) for f in open_rows[:TOP_FINDINGS]],
            open_findings=len(open_rows),
        ),
    )


@router.get("/repos", response_model=list[Repo])
def list_repos(store: Analyses, user_id: UserId, jobs: Jobs) -> list[Repo]:
    return [repo_view(store, jobs, r) for r in store.repos(user_id)]


@router.delete("/repos/{repo_id}", status_code=204)
def remove_repo(repo_id: str, store: Analyses, user_id: UserId, jobs: Jobs, settings: Config) -> Response:
    """Quita el repositorio del equipo y elimina su historial de análisis."""
    conn = store.conn
    membership(conn, user_id)
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        require_repo(store, user_id, repo_id)
        if membership(conn, user_id)["role"] != "owner":
            raise ApiError(403, "not_owner", "Solo quien administra el equipo puede quitar repositorios")
        if jobs.running_for_repo(conn, repo_id):
            raise ApiError(409, "already_running", "Espera a que termine el análisis o cancélalo antes de quitar el repositorio")
        delete_repo(conn, repo_id)
    jobs.forget_repo(repo_id)
    remove_repo_clones(settings, repo_id)
    try:
        remove_tree(Workspace(settings, repo_id).backup_root)
    except OSError:
        log.warning("No se pudieron limpiar los respaldos del repositorio %s", repo_id, exc_info=True)
    return Response(status_code=204)


@router.get("/repos/{repo_id}/history", response_model=list[HistoryPoint])
def repo_history(repo_id: str, store: Analyses, user_id: UserId, limit: int = Query(default=HISTORY_POINTS, ge=1, le=100)) -> list[HistoryPoint]:
    require_repo(store, user_id, repo_id)
    return history(store, repo_id, limit)
