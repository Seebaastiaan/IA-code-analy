"""Dependencias comunes: store de análisis, jobs en curso y acceso a repos limitado a su dueño."""

import sqlite3
from typing import Annotated

from fastapi import Depends

from app.analyses.store import AnalysisStore
from app.analysis.jobs import JobManager
from app.analysis.router import get_jobs
from app.auth import current_user_id
from app.db import get_db
from app.errors import ApiError
from app.teams.store import team_id_of


def get_analysis_store(conn: sqlite3.Connection = Depends(get_db)) -> AnalysisStore:
    return AnalysisStore(conn)


Analyses = Annotated[AnalysisStore, Depends(get_analysis_store)]
UserId = Annotated[str, Depends(current_user_id)]
Jobs = Annotated[JobManager, Depends(get_jobs)]


def repo_not_found() -> ApiError:
    return ApiError(404, "not_found", "Repositorio no encontrado")


def require_repo(store: AnalysisStore, user_id: str, repo_id: str) -> sqlite3.Row:
    """El repo si es del equipo del usuario; 404 (no 403) para no revelar que existe."""
    repo = store.repo(repo_id)
    if repo is None or repo["team_id"] != team_id_of(store.conn, user_id):
        raise repo_not_found()
    return repo
