"""
Contrato de datos del análisis: lo que el pipeline de analizadores entregará al terminar y que leen el
tablero, el reporte y el editor. Las categorías, severidades y herramientas son las de
docs/FRONTEND_SPEC.md §4 (frontend/src/features/findings/types.ts).
"""

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["alta", "media", "baja"]
Category = Literal["seg", "test", "prac"]
Tool = Literal["Bandit", "pip-audit", "pytest", "coverage", "Ruff", "Radon"]


@dataclass
class FindingInput:
    sev: Severity
    cat: Category
    tool: Tool
    rule: str
    file: str
    line: int
    msg: str
    why: str
    rec: str
    # Hay corrección automática (reglas de Ruff con corrección "safe")
    fix: bool = False
    # Texto de la línea señalada: permite reconocer el hallazgo aunque cambie de línea
    code: str | None = None


@dataclass
class CoverageInput:
    file: str
    percent: float


@dataclass
class ComplexityInput:
    fn: str
    file: str
    cc: int
    grade: str


@dataclass
class ReportInput:
    branch: str
    commit: str
    duration_s: float
    coverage_total: float
    tests_failed: int
    avg_complexity: float
    findings: list[FindingInput] = field(default_factory=list)
    coverage: list[CoverageInput] = field(default_factory=list)
    complexity: list[ComplexityInput] = field(default_factory=list)
    # ISO 8601; vacío = ahora
    created_at: str | None = None
