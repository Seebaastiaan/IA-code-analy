"""Convierte filas de SQLite en las respuestas del contrato."""

import json
import sqlite3
from typing import TYPE_CHECKING

from app.analyses.schemas import FindingCounts, Language, Progress, Repo, SavedReport
from app.analyses.store import AnalysisStore
from app.analysis.steps import JOB_STEPS

if TYPE_CHECKING:  # jobs importa el store: aquí solo se usa como tipo
    from app.analysis.jobs import JobManager


def report_view(store: AnalysisStore, row: sqlite3.Row, ignored: list[str]) -> SavedReport:
    return SavedReport(
        id=row["id"], num=row["num"], branch=row["branch"], commit=row["commit_sha"], created_at=row["created_at"],
        duration_s=row["duration_s"], languages=[Language(**lang) for lang in json.loads(row["languages"] or "[]")],
        findings=FindingCounts(**store.finding_counts(row["id"], ignored)),
    )


def repo_view(store: AnalysisStore, jobs: "JobManager", repo: sqlite3.Row) -> Repo:
    latest = store.latest_report(repo["id"])
    job = jobs.running_for_repo(store.conn, repo["id"])
    status, error = repo["status"], repo["error"]
    if status == "analizando" and job is None:
        # El servidor se reinició a mitad del análisis: el job en memoria se perdió
        status, error = ("listo", None) if latest else ("error", "El análisis se interrumpió. Vuelve a intentarlo.")
    total = store.conn.execute("SELECT COUNT(*) FROM reports WHERE repo_id = ?", (repo["id"],)).fetchone()[0]
    return Repo(
        id=repo["id"], name=repo["name"], url=repo["url"], branch=repo["branch"],
        commit=latest["commit_sha"] if latest else None,
        status=status,
        last_analyzed_at=latest["created_at"] if latest else None,
        files=repo["files"],
        last_report_id=latest["id"] if latest else None,
        last_report_num=latest["num"] if latest else None,
        reports=total,
        findings=FindingCounts(**store.finding_counts(latest["id"], store.config(repo["id"]).ignored)) if latest else None,
        error=error,
        progress=Progress(job_id=job.id, step=job.step, total=job.total, name=JOB_STEPS[min(job.step, job.total - 1)][0]) if job else None,
    )
