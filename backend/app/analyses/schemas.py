"""Modelos compartidos del contrato (frontend/src/shared/types/common.ts, features/repos/types.ts)."""

from typing import Literal

from pydantic import BaseModel


class Weights(BaseModel):
    seg: float
    test: float
    prac: float


class Thresholds(BaseModel):
    score: float
    cov: float


class Progress(BaseModel):
    job_id: str
    step: int
    total: int
    name: str


class FindingCounts(BaseModel):
    alta: int
    media: int
    baja: int


class Repo(BaseModel):
    id: str
    name: str
    url: str
    branch: str
    commit: str | None
    status: Literal["listo", "analizando", "error"]
    last_analyzed_at: str | None
    files: int
    last_report_id: str | None
    last_report_num: int | None
    # Análisis guardados del repo
    reports: int = 0
    # Hallazgos abiertos del último análisis por severidad
    findings: FindingCounts | None = None
    error: str | None
    progress: Progress | None = None


class Language(BaseModel):
    name: str
    files: int


class SavedReport(BaseModel):
    """Un análisis guardado en el repositorio (Sprint 5: con sus hallazgos de Seguridad, todavía sin score)."""

    id: str
    num: int
    branch: str
    commit: str
    created_at: str
    duration_s: int
    languages: list[Language]
    # Hallazgos abiertos de Bandit y pip-audit por severidad (sin las reglas ignoradas)
    findings: FindingCounts
