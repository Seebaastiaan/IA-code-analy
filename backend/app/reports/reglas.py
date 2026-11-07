"""
Reglas de negocio de un análisis (docs/adr/ADR-003-reglas-de-negocio.md): matriz regla → estado → evidencia.
Router aparte de reports/router.py para no mezclarse con el reporte (y sus cambios del Sprint 8).
"""

import json
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.analyses.access import Analyses, UserId
from app.analyses.reglas_store import RulesStore
from app.reports.router import find_report

router = APIRouter(prefix="/api/report", tags=["reportes"])


class RuleEvidence(BaseModel):
    file: str
    line: int
    text: str


class BusinessRuleResult(BaseModel):
    id: str
    title: str
    description: str
    severity: Literal["alta", "media", "baja"]
    paths: list[str]
    forbidden: str | None
    required: str | None
    # Trazabilidad con el tablero del equipo
    story: str | None
    owner: str | None
    criterion: str | None
    status: Literal["cumple", "no_cumple", "sin_verificar"]
    # Cómo se verificó: patron (prohibido/obligatorio) o ninguno (sin patrón; las pruebas llegan en el Sprint 8)
    level: str
    detail: str
    evidence: list[RuleEvidence]
    # Coincidencias totales (evidence guarda las primeras 20)
    evidence_total: int


class BusinessRulesSummary(BaseModel):
    total: int
    cumple: int
    no_cumple: int
    sin_verificar: int


class BusinessRules(BaseModel):
    report_id: str
    # False = el análisis es anterior a las reglas de negocio: hay que volver a analizar
    checked: bool
    # Archivo leído del repo (reglas_negocio.toml o docs/reglas_negocio.toml); None = no declara reglas
    source: str | None
    project: str | None
    # El archivo no es válido: no hay resultados
    error: str | None
    summary: BusinessRulesSummary
    rules: list[BusinessRuleResult]


@router.get("/{report_id}/reglas", response_model=BusinessRules)
def get_business_rules(report_id: str, store: Analyses, user_id: UserId, repo: str | None = Query(default=None, max_length=64)) -> BusinessRules:
    _, report = find_report(store, user_id, report_id, repo)
    rules = RulesStore(store.conn)
    check = rules.check(report["id"])
    rows = rules.results(report["id"]) if check else []
    results = [
        BusinessRuleResult(
            id=r["rule_id"], title=r["title"], description=r["description"], severity=r["severity"], paths=json.loads(r["paths"]),
            forbidden=r["forbidden"], required=r["required"], story=r["story"], owner=r["owner"], criterion=r["criterion"],
            status=r["status"], level=r["level"], detail=r["detail"], evidence=json.loads(r["evidence"]), evidence_total=r["evidence_total"],
        )
        for r in rows
    ]
    count = lambda status: sum(r.status == status for r in results)
    return BusinessRules(
        report_id=report["id"],
        checked=check is not None,
        source=check["source"] if check else None,
        project=check["project"] if check else None,
        error=check["error"] if check else None,
        summary=BusinessRulesSummary(total=len(results), cumple=count("cumple"), no_cumple=count("no_cumple"), sin_verificar=count("sin_verificar")),
        rules=results,
    )
