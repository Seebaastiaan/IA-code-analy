"""
Reglas de negocio de un análisis (docs/adr/ADR-003-reglas-de-negocio.md): matriz regla → estado → evidencia.
Router aparte de reports/router.py para no mezclarse con el reporte. La carga de reglas desde Configuración
está en app.projects.reglas.
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


class RuleTest(BaseModel):
    # nodeid de pytest (archivo::función)
    name: str
    file: str
    line: int
    # passed | failed | error | skipped | not_run (corrieron en el sandbox) o sin_ejecutar (leídas del código)
    outcome: str
    message: str


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
    status: Literal["cumple", "no_cumple", "prueba_rota", "no_implementada", "sin_verificar", "fuera_del_codigo"]
    # Cómo se verificó: pruebas, patron (prohibido/obligatorio), pruebas_y_patron o ninguno
    level: str
    detail: str
    evidence: list[RuleEvidence]
    # Coincidencias totales (evidence guarda las primeras 20)
    evidence_total: int
    # Pruebas ligadas (@pytest.mark.regla o test_rn###_…), las que fallan primero
    tests: list[RuleTest]


class BusinessRulesSummary(BaseModel):
    total: int
    cumple: int
    no_cumple: int
    sin_verificar: int
    # PROPUESTA_REGLAS_VERIFICABLES.md §9 (pruebas generadas): 0 en los reportes anteriores
    prueba_rota: int = 0
    no_implementada: int = 0
    fuera_del_codigo: int = 0


class BusinessRules(BaseModel):
    report_id: str
    # False = el análisis es anterior a las reglas de negocio: hay que volver a analizar
    checked: bool
    # Archivo leído del repo (reglas_negocio.toml o docs/reglas_negocio.toml); None = no declara reglas
    source: str | None
    # repo | app (cargadas en la app: el repo no tiene el archivo o el suyo no es válido)
    origin: Literal["repo", "app"] | None
    project: str | None
    # El archivo no es válido: no hay resultados
    error: str | None
    # El archivo del repo no era válido y se usaron las reglas corregidas en la app (origin = app)
    repo_error: str | None = None
    # Las pruebas corrieron en el sandbox; False = solo se encontraron leyendo el código
    tests_ran: bool
    warnings: list[str]
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
            tests=[RuleTest(**{k: t[k] for k in RuleTest.model_fields}) for t in json.loads(r["tests"] or "[]")],
        )
        for r in rows
    ]
    count = lambda status: sum(r.status == status for r in results)
    return BusinessRules(
        report_id=report["id"],
        checked=check is not None,
        source=check["source"] if check else None,
        origin=(check["origin"] or ("repo" if check["source"] else None)) if check else None,
        project=check["project"] if check else None,
        error=check["error"] if check else None,
        repo_error=check["repo_error"] if check else None,
        tests_ran=bool(check["tests_ran"]) if check else False,
        warnings=json.loads(check["warnings"] or "[]") if check else [],
        summary=BusinessRulesSummary(total=len(results), cumple=count("cumple"), no_cumple=count("no_cumple"), sin_verificar=count("sin_verificar"),
            prueba_rota=count("prueba_rota"), no_implementada=count("no_implementada"), fuera_del_codigo=count("fuera_del_codigo"),
        ),
        rules=results,
    )
