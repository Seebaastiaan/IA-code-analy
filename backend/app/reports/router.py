"""Reporte de un análisis y su exportación (docs/FRONTEND_SPEC.md §5.5 y §6.4)."""

import html
import json
import sqlite3
from typing import Literal

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel

from app.analyses.access import Analyses, UserId, require_repo
from app.analyses.schemas import Finding, Scores, Thresholds, Weights
from app.analyses.store import AnalysisStore
from app.analyses.views import finding_view, report_analyzers, report_scores, scores, visible
from app.analysis.pipeline import ALL_ANALYZERS
from app.errors import ApiError

router = APIRouter(prefix="/api/report", tags=["reportes"])

SARIF_LEVEL = {"alta": "error", "media": "warning", "baja": "note"}
SEV_LABEL = {"alta": "Alta", "media": "Media", "baja": "Baja"}
CAT_LABEL = {"seg": "Seguridad", "test": "Pruebas", "prac": "Buenas prácticas"}


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


# ─── Exportación ───


def to_markdown(r: Report) -> str:
    s = r.scores
    lines = [
        f"# {r.repo_name} · análisis #{r.num}",
        "",
        f"Rama `{r.branch}` · commit `{r.commit}` · {r.created_at}",
        "",
        "| Score global | Seguridad | Pruebas | Buenas prácticas |",
        "|---|---|---|---|",
        f"| **{s.global_}** | {s.seg} | {s.test} | {s.prac} |",
        "",
        (f"Cobertura {r.summary.coverage_total} %" if r.summary.coverage_total is not None else "Cobertura no medida")
        + f" · {r.summary.tests_failed} prueba(s) fallan · complejidad media {r.summary.avg_complexity}",
        "",
        "## Hallazgos",
        "",
    ]
    if not r.findings:
        lines.append("Sin hallazgos.")
    for f in r.findings:
        estado = " *(resuelto)*" if f.status == "resolved" else ""
        lines += [f"- **{SEV_LABEL[f.sev]}** · {f.tool} `{f.rule}` · `{f.file}:{f.line}`{estado}", f"  {f.msg}", f"  - Cómo corregirlo: {f.rec}"]
    return "\n".join(lines) + "\n"


def to_html(r: Report) -> str:
    e = html.escape
    s = r.scores
    rows = "".join(
        f"<tr class='{e(f.status)}'><td>{e(SEV_LABEL[f.sev])}</td><td>{e(CAT_LABEL[f.cat])}</td><td>{e(f.tool)} <code>{e(f.rule)}</code></td>"
        f"<td><code>{e(f.file)}:{f.line}</code></td><td>{e(f.msg)}<br><small>{e(f.rec)}</small></td></tr>"
        for f in r.findings
    )
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(r.repo_name)} · análisis #{r.num}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#0f172a}}
table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #e2e8f0;padding:.5rem;text-align:left;vertical-align:top}}
.kpi{{display:flex;gap:1rem;flex-wrap:wrap}}.kpi div{{border:1px solid #e2e8f0;border-radius:.75rem;padding:.75rem 1rem}}
tr.resolved{{opacity:.6;text-decoration:line-through}}small{{color:#475569}}
</style></head><body>
<h1>{e(r.repo_name)} · análisis #{r.num}</h1>
<p>Rama <code>{e(r.branch)}</code> · commit <code>{e(r.commit)}</code> · {e(r.created_at)}</p>
<div class="kpi"><div><b>Score global</b><br>{s.global_}</div><div>Seguridad<br>{s.seg}</div><div>Pruebas<br>{s.test}</div><div>Buenas prácticas<br>{s.prac}</div></div>
<h2>Hallazgos ({len(r.findings)})</h2>
<table><thead><tr><th>Severidad</th><th>Categoría</th><th>Regla</th><th>Ubicación</th><th>Detalle</th></tr></thead><tbody>{rows}</tbody></table>
</body></html>
"""


def to_sarif(r: Report) -> str:
    rules = {f.rule: {"id": f.rule, "shortDescription": {"text": f.msg}, "help": {"text": f.rec}} for f in r.findings}
    results = [
        {
            "ruleId": f.rule,
            "level": SARIF_LEVEL[f.sev],
            "message": {"text": f.msg},
            "locations": [{"physicalLocation": {"artifactLocation": {"uri": f.file}, "region": {"startLine": f.line}}}],
            "properties": {"tool": f.tool, "category": f.cat, "status": f.status},
        }
        for f in r.findings
    ]
    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "IA voy", "rules": list(rules.values())}}, "results": results}],
    }
    return json.dumps(sarif, ensure_ascii=False, indent=2)


EXPORTERS = {
    "json": (lambda r: r.model_dump_json(indent=2), "application/json", "json"),
    "md": (to_markdown, "text/markdown; charset=utf-8", "md"),
    "html": (to_html, "text/html; charset=utf-8", "html"),
    "sarif": (to_sarif, "application/sarif+json", "sarif.json"),
}


@router.get("/{report_id}/export")
def export_report(report_id: str, store: Analyses, user_id: UserId, format: Literal["json", "md", "html", "sarif"] = "json", repo: str | None = Query(default=None, max_length=64)) -> Response:
    repo_row, report = find_report(store, user_id, report_id, repo)
    render, media_type, ext = EXPORTERS[format]
    body = render(build_report(store, repo_row, report))
    # Se descarga como adjunto: el HTML no se renderiza en el origen de la API
    filename = f"reporte-{report['id']}.{ext}"
    return Response(body, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"', "X-Content-Type-Options": "nosniff"})
