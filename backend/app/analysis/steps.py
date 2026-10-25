"""
Pasos del análisis en el Sprint 5 (mismo orden que frontend/src/features/analysis/constants/jobSteps.ts).

El análisis llega hasta pip-audit: clona, crea el entorno, instala las dependencias y corre los dos
analizadores de Seguridad (Bandit y pip-audit). pytest, coverage, Ruff, Radon y el score entran en el
Sprint 6; el índice del asistente, en el Sprint 7.
"""

CLONE_STEP, VENV_STEP, INSTALL_STEP, BANDIT_STEP, AUDIT_STEP = 0, 1, 2, 3, 4

JOB_STEPS: list[tuple[str, str]] = [
    ("Clonando repositorio", "git clone --depth 1 --branch {branch} {url}"),
    ("Creando entorno aislado", "uv venv .venv  (sandbox)"),
    ("Instalando dependencias", "uv pip install -r requirements.txt"),
    ("Bandit", "bandit -r . -f json"),
    ("pip-audit", "pip-audit --path .venv/…/site-packages -f json"),
]
