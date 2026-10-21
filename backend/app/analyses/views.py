"""Convierte filas de SQLite en las respuestas del contrato, aplicando reglas ignoradas y el score."""

import json
import sqlite3
from typing import TYPE_CHECKING

from app.analyses.schemas import Finding, Progress, Repo, Scores
from app.analyses.scoring import category_scores, effective_coverage, global_score
from app.analyses.store import AnalysisStore, ProjectConfig
from app.analyses.workspace import is_excluded
from app.analysis.fake import JOB_STEPS

if TYPE_CHECKING:  # jobs importa este módulo: solo se usa como tipo
    from app.analysis.jobs import JobManager

SEV_ORDER = {"alta": 0, "media": 1, "baja": 2}


def visible(rows: list[sqlite3.Row], cfg: ProjectConfig) -> list[sqlite3.Row]:
    """Hallazgos sin las reglas ignoradas ni las rutas excluidas, ordenados por severidad."""
    ignored = set(cfg.ignored)
    keep = (r for r in rows if r["rule"] not in ignored and not is_excluded(r["file"], cfg.excluded))
    return sorted(keep, key=lambda r: (SEV_ORDER[r["sev"]], r["id"]))


def scores(report: sqlite3.Row, findings: list[sqlite3.Row], cfg: ProjectConfig) -> Scores:
    """Score del reporte con sus hallazgos abiertos y no ignorados (`findings` ya filtrados con `visible`)."""
    if report["coverage_total"] < 0:
        # Reporte anterior a los analizadores reales: solo tiene las categorías guardadas
        cats = {k: float(report[k]) for k in ("seg", "test", "prac")}
    else:
        cov = effective_coverage(report["coverage_total"], report_analyzers(report))
        cats = category_scores(((f["cat"], f["sev"]) for f in findings if f["status"] == "open"), cov, report["tests_failed"], report["code_lines"])
    return Scores(**cats, global_=global_score(cfg.weights, cats))


def report_analyzers(report: sqlite3.Row) -> list[str]:
    """Analizadores que corrieron en el reporte (vacío = todos: reportes anteriores a poder elegirlos)."""
    return json.loads(report["analyzers"] or "[]")


def report_scores(store: AnalysisStore, report: sqlite3.Row, cfg: ProjectConfig) -> Scores:
    return scores(report, visible(store.findings(report["id"]), cfg), cfg)


def finding_view(row: sqlite3.Row, with_code: bool = True) -> Finding:
    return Finding(
        id=row["id"], sev=row["sev"], cat=row["cat"], tool=row["tool"], rule=row["rule"], file=row["file"], line=row["line"],
        msg=row["msg"], why=row["why"], rec=row["rec"], fix=bool(row["fix"]), status=row["status"],
        snippet=json.loads(row["snippet"]) if with_code and row["snippet"] else None,
    )


def repo_view(store: AnalysisStore, jobs: "JobManager", repo: sqlite3.Row) -> Repo:
    latest = store.latest_report(repo["id"])
    job = jobs.running_for_repo(store.conn, repo["id"])
    status, error = repo["status"], repo["error"]
    if status == "analizando" and job is None:
        # El servidor se reinició a mitad del análisis: el job en memoria se perdió
        status, error = ("listo", None) if latest else ("error", "El análisis se interrumpió. Vuelve a intentarlo.")
    return Repo(
        id=repo["id"], name=repo["name"], url=repo["url"], branch=repo["branch"],
        commit=latest["commit_sha"] if latest else None,
        status=status,
        last_analyzed_at=latest["created_at"] if latest else None,
        files=repo["files"],
        last_report_id=latest["id"] if latest else None,
        last_report_num=latest["num"] if latest else None,
        scores=report_scores(store, latest, store.config(repo["id"])) if latest else None,
        error=error,
        progress=Progress(job_id=job.id, step=job.step, total=job.total, name=JOB_STEPS[min(job.step, job.total - 1)][0]) if job else None,
    )
