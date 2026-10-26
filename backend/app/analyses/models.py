"""
Lo que el job de análisis (app.analysis.jobs) entrega al terminar (ver `AnalysisStore.save_report`).
Es el contrato entre el análisis y los módulos que lo leen: tablero, reporte y editor.
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
    # Hay corrección automática (hoy solo reglas de Ruff con corrección "safe")
    fix: bool = False
    # Texto de la línea señalada; si se omite, save_report lo toma de la copia de trabajo
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
    # Semilla de las métricas que aún se simulan (pruebas y cobertura): el mismo reporte se ve igual siempre
    seed: int = 0
    # Analizadores que corrieron; vacío = todos
    analyzers: list[str] = field(default_factory=list)
    # Lenguajes del repo [{name, files}] (solo se analiza Python)
    languages: list[dict] = field(default_factory=list)
    # Líneas de Python analizadas: escalan la penalización del score en proyectos grandes
    code_lines: int = 0
