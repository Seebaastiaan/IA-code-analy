"""
Pasos 2-10 del análisis sobre el clon (motor determinista, docs/adr/ADR-001):
- Ruff y Bandit (hallazgos) y Radon (complejidad): reales. Solo leen el código y corren en el backend
  (`analyze_static`).
- pip-audit, pytest y coverage ejecutan el código del repo y necesitan un sandbox (Sprint 5). Mientras tanto se
  SIMULAN: sus números salen de la semilla del job (el mismo reporte siempre se ve igual) y sus hallazgos dicen
  "(simulado)" para no confundirse con resultados reales.
"""

import random
from dataclasses import dataclass

from app.analyses.analyzers import complexity, is_test_path, static_findings_dir
from app.analyses.models import ComplexityInput, CoverageInput, FindingInput, ReportInput
from app.analyses.scoring import category_scores, global_score
from app.analyses.store import AnalysisStore, ProjectConfig
from app.analyses.workspace import Workspace
from app.config import Settings
from app.db import session

# Índices de fake.JOB_STEPS
VENV_STEP, INSTALL_STEP, BANDIT_STEP, AUDIT_STEP, PYTEST_STEP, COVERAGE_STEP = 1, 2, 3, 4, 5, 6

# Los seis analizadores (frontend: features/analysis/constants/jobSteps.ts)
ALL_ANALYZERS = ("bandit", "pip-audit", "pytest", "coverage", "ruff", "radon")
SIMULATED = "  (simulado) se ejecutará en el sandbox"


@dataclass
class StaticResult:
    """Lo que sale de leer el código (Ruff, Bandit, Radon), sin ejecutarlo."""

    files: list[str]
    py: list[str]
    findings: list[FindingInput]
    complexity: list[ComplexityInput]
    cfg: ProjectConfig
    # Líneas de Python analizadas (escala del score)
    code_lines: int = 0


@dataclass
class PipelineResult:
    report: ReportInput
    passed: int
    score: float


_is_test = is_test_path


# Archivos de herramientas (empaquetado, tareas, configuración de pruebas, docs): no son código que se pruebe
TOOLING = {"setup.py", "noxfile.py", "fabfile.py", "tasks.py", "conftest.py", "manage.py"}


def _is_tooling(path: str) -> bool:
    return path.rsplit("/", 1)[-1] in TOOLING or path.startswith(("docs/", "doc/"))


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, round(v)))


def simulated_tests(py_files: list[str], rng: random.Random, base: float, min_cov: float) -> tuple[list[CoverageInput], float, int, int, list[FindingInput]]:
    """(cobertura por archivo, cobertura total, fallidas, pasadas, hallazgos) simulados alrededor de `base`."""
    code = [f for f in py_files if not _is_test(f) and not _is_tooling(f)]
    tests = [f for f in py_files if _is_test(f)]
    coverage = sorted((CoverageInput(file=f, percent=_clamp(base + rng.randint(-30, 15))) for f in code), key=lambda c: c.percent)
    total = round(sum(c.percent for c in coverage) / len(coverage), 1) if coverage else 0.0
    failed = 0 if not tests else rng.choice([0, 0, 1, 1, 2]) if base >= 70 else rng.choice([1, 2, 3])
    passed = rng.randint(5, 40) * max(1, len(tests)) if tests else 0
    findings = [
        FindingInput(
            sev="media" if c.percent < min_cov - 15 else "baja", cat="test", tool="coverage", rule="COV", file=c.file, line=1, code="",
            msg=f"Cobertura de {c.percent:.0f} % (mínimo {min_cov:.0f} %) (simulado)",
            why="Las líneas sin probar pueden romperse sin que ninguna prueba lo detecte.",
            rec="Agrega pruebas para las ramas sin cubrir. Este valor es simulado hasta que las pruebas corran en el sandbox.",
        )
        for c in coverage
        if c.percent < min_cov
    ]
    if failed and tests:
        findings.append(FindingInput(
            sev="alta", cat="test", tool="pytest", rule="FAIL", file=rng.choice(tests), line=1, code="",
            msg=f"{failed} prueba(s) fallaron (simulado)",
            why="Una prueba que falla indica una regresión o una prueba desactualizada.",
            rec="Ejecuta `pytest -x` localmente. Este resultado es simulado hasta que las pruebas corran en el sandbox.",
        ))
    return coverage, total, failed, passed, findings


def analyze_static(settings: Settings, repo_id: str) -> StaticResult:
    """Ruff, Bandit y Radon sobre el clon. Bloqueante: el job lo llama con asyncio.to_thread."""
    ws = Workspace(settings, repo_id)
    with session(settings.database_path) as conn:
        cfg = AnalysisStore(conn).config(repo_id)
    files = ws.list_files(cfg.excluded)
    py = [f for f in files if f.endswith(".py")]
    findings = static_findings_dir(ws.root, files)
    lines = sum(len(lines) for f in py if (lines := ws.read_lines(f)))
    return StaticResult(files=files, py=py, findings=findings, complexity=complexity(ws.root, py), cfg=cfg, code_lines=lines)


def build(settings: Settings, repo_id: str, static: StaticResult, branch: str, commit: str | None, seed: int, cat: dict) -> PipelineResult:
    """Reporte con los hallazgos reales de Ruff y Bandit, la complejidad de Radon y las pruebas simuladas."""
    cfg = static.cfg
    coverage, cov_total, failed, passed, test_findings = simulated_tests(static.py, random.Random(seed), cat["test"], cfg.thresholds["cov"])
    findings = static.findings + test_findings
    cc = static.complexity
    report = ReportInput(
        branch=branch, commit=commit or "0000000", duration_s=0, coverage_total=cov_total, tests_failed=failed,
        avg_complexity=round(sum(c.cc for c in cc) / len(cc), 1) if cc else 0.0,
        findings=findings, coverage=coverage, complexity=cc, seed=seed, code_lines=static.code_lines,
    )
    ignored = set(cfg.ignored)
    cats = category_scores(((f.cat, f.sev) for f in findings if f.rule not in ignored), cov_total, failed, static.code_lines)
    return PipelineResult(report=report, passed=passed, score=global_score(cfg.weights, cats))


# ───────────────────────── Líneas de la terminal ─────────────────────────


def step_summary(step: int, r: PipelineResult | None) -> str | None:
    """Línea de resultado que muestra la terminal al terminar cada paso (índices de fake.JOB_STEPS)."""
    if step in (VENV_STEP, INSTALL_STEP, AUDIT_STEP) or r is None:
        return SIMULATED
    f = r.report.findings
    bandit = [x for x in f if x.tool == "Bandit"]
    ruff = [x for x in f if x.tool == "Ruff"]
    lines = {
        3: f"  {sum(x.sev == 'alta' for x in bandit)} alta · {sum(x.sev == 'media' for x in bandit)} media · {sum(x.sev == 'baja' for x in bandit)} baja",
        5: f"  {r.passed} passed, {r.report.tests_failed} failed (simulado)",
        6: f"  cobertura total: {r.report.coverage_total} % (simulado)",
        7: f"  {len(ruff)} problema(s) ({sum(x.fix for x in ruff)} con corrección automática)",
        8: f"  complejidad media: {r.report.avg_complexity} · {len(r.report.complexity)} funciones",
        9: f"  score global: {r.score}",
    }
    return lines.get(step)
