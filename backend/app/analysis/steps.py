"""
Pasos del análisis en el Sprint 4 (mismo orden que frontend/src/features/analysis/constants/jobSteps.ts).

El análisis llega hasta "Creando entorno aislado". Instalar dependencias, los analizadores (Bandit,
pip-audit, pytest, coverage, Ruff, Radon), el score y el índice del asistente entran en los siguientes sprints.
"""

CLONE_STEP, VENV_STEP = 0, 1

JOB_STEPS: list[tuple[str, str]] = [
    ("Clonando repositorio", "git clone --depth 1 --branch {branch} {url}"),
    ("Creando entorno aislado", "uv venv .venv  (sandbox)"),
]
