"""Reporte de un análisis (docs/FRONTEND_SPEC.md §5.5 y §6.4)."""

import json
import sqlite3

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.analyses.access import Analyses, UserId, require_repo
from app.analyses.schemas import Finding, Scores, Thresholds, Weights
from app.analyses.store import AnalysisStore
from app.analyses.views import finding_view, report_analyzers, report_scores, scores, visible
from app.analysis.pipeline import ALL_ANALYZERS
from app.errors import ApiError

router = APIRouter(prefix="/api/report", tags=["reportes"])

class PrevReport(BaseModel):
    num: int
    scores: Scores


class CoverageEntry(BaseModel):
    file: str
    percent: float


class ComplexityEntry(BaseModel):
    fn: str
    file: str
    cc: int
    grade: str


class LanguageCount(BaseModel):
    name: str
    files: int


class Summary(BaseModel):
    # None = no se eligió coverage en ese análisis
    coverage_total: float | None
    tests_failed: int
    avg_complexity: float


class Report(BaseModel):
    id: str
    num: int
    repo_id: str
    repo_name: str
    branch: str
    commit: str
    created_at: str
    duration_s: float
    scores: Scores
    prev: PrevReport | None
    weights: Weights
    thresholds: Thresholds
    findings: list[Finding]
    coverage: list[CoverageEntry]
    complexity: list[ComplexityEntry]
    summary: Summary
    # Analizadores que corrieron (los no elegidos no tienen hallazgos ni métricas)
    analyzers: list[str]
    # Lenguajes del repo (solo se analiza Python); vacío en reportes anteriores
    languages: list[LanguageCount]


def find_report(store: AnalysisStore, user_id: str, report_id: str, repo_id: str | None) -> tuple[sqlite3.Row, sqlite3.Row]:
    """(repo, reporte). `report_id` = "{repo}-{num}" o "latest" junto con `?repo=`."""
    if report_id == "latest":
        if not repo_id:
            raise ApiError(422, "invalid_request", "repo: requerido con report_id = latest")
        repo = require_repo(store, user_id, repo_id)
        report = store.latest_report(repo["id"])
    else:
        report = store.report(report_id)
        if report is None:
            raise ApiError(404, "not_found", "Reporte no encontrado")
        repo = require_repo(store, user_id, report["repo_id"])
    if report is None:
        raise ApiError(404, "not_found", "Este repositorio aún no tiene reportes")
    return repo, report


def build_report(store: AnalysisStore, repo: sqlite3.Row, report: sqlite3.Row) -> Report:
    cfg = store.config(repo["id"])
    rows = visible(store.findings(report["id"]), cfg)
    prev = store.previous_report(repo["id"], report["num"])
    ran = report_analyzers(report) or list(ALL_ANALYZERS)
    return Report(
        id=report["id"],
        num=report["num"],
        repo_id=repo["id"],
        repo_name=repo["name"],
        branch=report["branch"],
        commit=report["commit_sha"],
        created_at=report["created_at"],
        duration_s=report["duration_s"],
        scores=scores(report, rows, cfg),
        prev=PrevReport(num=prev["num"], scores=report_scores(store, prev, cfg)) if prev else None,
        weights=Weights(**cfg.weights),
        thresholds=Thresholds(**cfg.thresholds),
        findings=[finding_view(f) for f in rows],
        coverage=json.loads(report["coverage"]),
        complexity=json.loads(report["complexity"]),
        summary=Summary(coverage_total=report["coverage_total"] if "coverage" in ran else None, tests_failed=report["tests_failed"], avg_complexity=report["avg_complexity"]),
        analyzers=ran,
        languages=json.loads(report["languages"] or "[]"),
    )


@router.get("/{report_id}", response_model=Report)
def get_report(report_id: str, store: Analyses, user_id: UserId, repo: str | None = Query(default=None, max_length=64)) -> Report:
    repo_row, report = find_report(store, user_id, report_id, repo)
    return build_report(store, repo_row, report)
