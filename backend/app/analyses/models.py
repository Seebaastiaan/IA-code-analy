"""
Lo que el job de análisis (app.analysis.jobs) entrega al terminar (ver `AnalysisStore.save_report`).
En el Sprint 5 son los hallazgos de Seguridad (Bandit y pip-audit); cobertura, complejidad y el resto de
las métricas llegan con los analizadores del Sprint 6.
"""

from dataclasses import dataclass
from typing import Literal

Severity = Literal["alta", "media", "baja"]
Category = Literal["seg", "test", "prac"]
Tool = Literal["Bandit", "pip-audit"]


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
    # Texto de la línea señalada; si se omite, save_report lo toma de la copia de trabajo
    code: str | None = None
