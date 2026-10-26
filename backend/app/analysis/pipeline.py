"""
Pasos 2-10 del análisis sobre el clon:
- Ruff y Bandit (hallazgos) y Radon (complejidad): siempre reales. Solo leen el código y corren en el backend
  (`analyze_static`).
- pip-audit, pytest y coverage: ejecutan el código del repo, así que corren en el sandbox
  (app.analysis.sandbox) cuando `SANDBOX` es `wsl` o `docker`. Con `SANDBOX=off`, o si el sandbox no está
  disponible, se SIMULAN: sus números salen de la semilla del job (el mismo reporte siempre se ve igual)
  y sus hallazgos dicen "(simulado)" para no confundirse con resultados reales.
"""

import logging
import random
import re
from dataclasses import dataclass

from app.analyses.analyzers import complexity, is_test_path, static_findings_dir
from app.analyses.config_file import FILENAME, ConfigError, from_toml
from app.analyses.models import ComplexityInput, CoverageInput, FindingInput, ReportInput
from app.analyses.scoring import category_scores, effective_coverage, global_score
from app.analyses.store import AnalysisStore, ProjectConfig
from app.analyses.workspace import Workspace, is_excluded
from app.analysis.sandbox import PhaseResult, SandboxOutput, parse_audit, parse_coverage, parse_junit
from app.config import Settings
from app.db import session

log = logging.getLogger(__name__)

# Índices de fake.JOB_STEPS
VENV_STEP, INSTALL_STEP, BANDIT_STEP, AUDIT_STEP, PYTEST_STEP, COVERAGE_STEP = 1, 2, 3, 4, 5, 6
# Fase del sandbox con la que termina cada paso
SANDBOX_PHASE = {VENV_STEP: "venv", INSTALL_STEP: "install", AUDIT_STEP: "audit", PYTEST_STEP: "tests", COVERAGE_STEP: "coverage"}
MAX_TEST_FINDINGS = 50

# Analizadores que se pueden elegir en "Nuevo análisis" (frontend: features/analysis/constants/jobSteps.ts)
ALL_ANALYZERS = ("bandit", "pip-audit", "pytest", "coverage", "ruff", "radon")
CATEGORY_ANALYZERS = {"seg": ("bandit", "pip-audit"), "test": ("pytest", "coverage"), "prac": ("ruff", "radon")}
# Los que ejecutan código del repo (necesitan el sandbox)
SANDBOX_ANALYZERS = {"pip-audit", "pytest", "coverage"}
# Paso de la terminal de cada analizador (índices de fake.JOB_STEPS)
ANALYZER_STEP = {3: "bandit", 4: "pip-audit", 5: "pytest", 6: "coverage", 7: "ruff", 8: "radon"}
OMITTED = "  omitido (no seleccionado)"


def chosen(step: int, analyzers: set[str]) -> bool:
    """El paso corre: no es de un analizador o su analizador se eligió."""
    return ANALYZER_STEP.get(step) is None or ANALYZER_STEP[step] in analyzers


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
    # pytest, coverage y pip-audit se simularon (sin sandbox)
    simulated: bool = True
    vulnerable: int = 0


_is_test = is_test_path


# Archivos de herramientas (empaquetado, tareas, configuración de pruebas, docs): no son código que se pruebe
TOOLING = {"setup.py", "noxfile.py", "fabfile.py", "tasks.py", "conftest.py", "manage.py"}


def _is_tooling(path: str) -> bool:
    return path.rsplit("/", 1)[-1] in TOOLING or path.startswith(("docs/", "doc/"))


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, round(v)))


def _last_line(text: str, default: str) -> str:
    lines = text.strip().splitlines()
    return lines[-1] if lines else default


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
            rec="Agrega pruebas para las ramas sin cubrir. Este valor es simulado: activa el sandbox (SANDBOX=wsl o docker) para medirlo.",
        )
        for c in coverage
        if c.percent < min_cov
    ]
    if failed and tests:
        findings.append(FindingInput(
            sev="alta", cat="test", tool="pytest", rule="FAIL", file=rng.choice(tests), line=1, code="",
            msg=f"{failed} prueba(s) fallaron (simulado)",
            why="Una prueba que falla indica una regresión o una prueba desactualizada.",
            rec="Ejecuta `pytest -x` localmente. Este resultado es simulado: activa el sandbox (SANDBOX=wsl o docker) para correr las pruebas.",
        ))
    return coverage, total, failed, passed, findings


def import_repo_config(store: AnalysisStore, ws: Workspace, repo_id: str) -> None:
    """Primer análisis de un repo que trae su propio `.ia_voy.toml`: se adopta. Después manda la pantalla Configuración."""
    path = ws.root / FILENAME
    if store.has_config(repo_id) or not path.is_file():
        return
    try:
        store.save_config(repo_id, from_toml(path.read_text(encoding="utf-8", errors="replace"), store.config(repo_id)))
    except ConfigError as exc:
        log.warning("Se ignora %s de %s: %s", FILENAME, repo_id, exc)


def analyze_static(settings: Settings, repo_id: str, analyzers: list[str] | tuple[str, ...] = ALL_ANALYZERS) -> StaticResult:
    """Ruff, Bandit y Radon (los elegidos) sobre el clon. Bloqueante: el job lo llama con asyncio.to_thread."""
    ws = Workspace(settings, repo_id)
    with session(settings.database_path) as conn:
        store = AnalysisStore(conn)
        import_repo_config(store, ws, repo_id)
        cfg = store.config(repo_id)
    files = ws.list_files(cfg.excluded)
    py = [f for f in files if f.endswith(".py")]
    findings = static_findings_dir(ws.root, files, ruff_on="ruff" in analyzers, bandit_on="bandit" in analyzers)
    lines = sum(len(lines) for f in py if (lines := ws.read_lines(f)))
    return StaticResult(files=files, py=py, findings=findings, complexity=complexity(ws.root, py) if "radon" in analyzers else [], cfg=cfg, code_lines=lines)


# ───────────────────────── Resultados del sandbox ─────────────────────────


def _deps_file(files: list[str]) -> str:
    return next((f for f in ("requirements.txt", "pyproject.toml", "setup.py") if f in files), "requirements.txt")


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _package_line(lines: list[str] | None, package: str) -> int:
    """Línea del archivo de dependencias que menciona el paquete (1 si no aparece: es una dependencia indirecta)."""
    target = _normalize(package)
    for i, text in enumerate(lines or [], start=1):
        m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", text)
        if m and _normalize(m.group(1)) == target:
            return i
    return 1


def audit_findings(ws: Workspace, files: list[str], out: SandboxOutput) -> list[FindingInput]:
    deps = _deps_file(files)
    lines = ws.read_lines(deps) if deps in files else None
    findings = []
    for v in parse_audit(out.audit):
        fix = f"Actualizar a {v.package} {v.fix_versions[0]} o superior" if v.fix_versions else "No hay versión corregida publicada: evalúa reemplazar el paquete"
        findings.append(FindingInput(
            sev="alta", cat="seg", tool="pip-audit", rule=f"{v.package} {v.version}", file=deps, line=_package_line(lines, v.package),
            msg=f"{v.package} {v.version} tiene {len(v.ids)} vulnerabilidad(es) conocida(s): {', '.join(v.ids[:5])}",
            why=v.description[:400] or "La versión instalada tiene avisos de seguridad publicados.",
            rec=f"{fix} y volver a correr las pruebas.",
        ))
    return findings


def real_tests(static: StaticResult, out: SandboxOutput, min_cov: float) -> tuple[list[CoverageInput], float, int, int, list[FindingInput]]:
    """(cobertura por archivo, cobertura total, fallidas, pasadas, hallazgos) de pytest y coverage en el sandbox."""
    findings: list[FindingInput] = []
    install, tests = out.phases.get("install"), out.phases.get("tests")
    deps = _deps_file(static.files)
    if install is not None and not install.ok:
        findings.append(FindingInput(
            sev="alta", cat="test", tool="pytest", rule="DEPS", file=deps, line=1, code="",
            msg="No se pudieron instalar las dependencias del proyecto",
            why=f"Sin dependencias las pruebas no pueden importar el código. Salida de la instalación:\n{install.log_tail[-600:]}",
            rec="Revisa que requirements.txt (o pyproject.toml) tenga versiones que existan y se instalen en Python 3.12.",
        ))

    run = parse_junit(out.junit)
    for case in run.failures[:MAX_TEST_FINDINGS]:
        if is_excluded(case.file, static.cfg.excluded):
            continue
        what = "falló" if case.kind == "failure" else "terminó con error"
        findings.append(FindingInput(
            sev="alta", cat="test", tool="pytest", rule="FAIL" if case.kind == "failure" else "ERROR", file=case.file, line=case.line,
            msg=f"{case.name} {what}" + (f": {case.message}" if case.message else ""),
            why="Una prueba que falla indica una regresión o una prueba desactualizada.",
            rec=f"Ejecuta `pytest {case.file}::{case.name.split('[')[0]} -x` localmente para ver el detalle.",
        ))
    # pytest: 0 todo bien, 1 fallaron pruebas, 5 no encontró pruebas; otro código = no pudo correr
    if tests is not None and tests.code not in (0, 1, 5) and not run.failures:
        test_files = [f for f in static.py if _is_test(f)]
        reason = " (tiempo agotado)" if tests.code == 124 else f" (código {tests.code})" if tests.code is not None else ""
        findings.append(FindingInput(
            sev="alta", cat="test", tool="pytest", rule="ERROR", file=test_files[0] if test_files else deps, line=1, code="",
            msg=f"pytest no pudo correr las pruebas{reason}",
            why=f"Salida de pytest:\n{tests.log_tail[-600:]}",
            rec="Ejecuta `pytest` localmente en un entorno limpio con las dependencias del proyecto.",
        ))

    measured = parse_coverage(out.coverage)
    coverage, covered, statements = [], 0, 0
    for f in static.py:
        if _is_test(f) or _is_tooling(f):
            continue
        if f not in measured:
            # Ninguna prueba lo importó: coverage no lo midió
            coverage.append(CoverageInput(file=f, percent=0.0))
            continue
        done, total = measured[f]
        covered, statements = covered + done, statements + total
        coverage.append(CoverageInput(file=f, percent=_clamp(100 * done / total) if total else 100.0))
    coverage.sort(key=lambda c: c.percent)
    cov_total = round(100 * covered / statements, 1) if statements else 0.0
    findings += [
        FindingInput(
            sev="media" if c.percent < min_cov - 15 else "baja", cat="test", tool="coverage", rule="COV", file=c.file, line=1, code="",
            msg=f"Cobertura de {c.percent:.0f} % (mínimo {min_cov:.0f} %)",
            why="Las líneas sin probar pueden romperse sin que ninguna prueba lo detecte.",
            rec="Agrega pruebas para las ramas sin cubrir (`coverage report -m` muestra las líneas que faltan).",
        )
        for c in coverage
        if c.percent < min_cov
    ]
    failed = run.failed or (1 if any(f.rule in ("ERROR", "DEPS") for f in findings) else 0)
    return coverage, cov_total, failed, run.passed, findings


def build(
    settings: Settings, repo_id: str, static: StaticResult, out: SandboxOutput | None, branch: str, commit: str | None, seed: int, cat: dict,
    analyzers: list[str] | tuple[str, ...] = ALL_ANALYZERS,
) -> PipelineResult:
    """
    Reporte con lo estático y lo del sandbox; sin sandbox (o si no pudo crear el entorno), simula las pruebas.
    Solo entra lo de los analizadores elegidos: sin pytest no hay pruebas que fallan, sin coverage la
    cobertura queda "no medida" (el score de pruebas solo descuenta las que fallan).
    """
    cfg = static.cfg
    vulns: list[FindingInput] = []
    if out is not None and out.usable:
        vulns = audit_findings(Workspace(settings, repo_id), static.files, out) if "pip-audit" in analyzers else []
        coverage, cov_total, failed, passed, test_findings = real_tests(static, out, cfg.thresholds["cov"])
        simulated = False
    else:
        coverage, cov_total, failed, passed, test_findings = simulated_tests(static.py, random.Random(seed), cat["test"], cfg.thresholds["cov"])
        simulated = True
    if "pytest" not in analyzers:
        failed, passed = 0, 0
        test_findings = [f for f in test_findings if f.tool != "pytest"]
    if "coverage" not in analyzers:
        coverage, cov_total = [], 0.0
        test_findings = [f for f in test_findings if f.tool != "coverage"]
    findings = static.findings + vulns + test_findings
    cc = static.complexity
    report = ReportInput(
        branch=branch, commit=commit or "0000000", duration_s=0, coverage_total=cov_total, tests_failed=failed,
        avg_complexity=round(sum(c.cc for c in cc) / len(cc), 1) if cc else 0.0,
        findings=findings, coverage=coverage, complexity=cc, seed=seed, analyzers=list(analyzers), code_lines=static.code_lines,
    )
    ignored = set(cfg.ignored)
    cats = category_scores(((f.cat, f.sev) for f in findings if f.rule not in ignored), effective_coverage(cov_total, analyzers), failed, static.code_lines)
    return PipelineResult(report=report, passed=passed, score=global_score(cfg.weights, cats), simulated=simulated, vulnerable=len(vulns))


def run(settings: Settings, repo_id: str, branch: str, commit: str | None, seed: int, cat: dict) -> PipelineResult:
    """Análisis completo sin sandbox (pruebas simuladas). Bloqueante."""
    return build(settings, repo_id, analyze_static(settings, repo_id), None, branch, commit, seed, cat)


# ───────────────────────── Líneas de la terminal ─────────────────────────


def phase_summary(step: int, phase: PhaseResult, out: SandboxOutput) -> str:
    """Línea de la terminal al terminar un paso que corrió en el sandbox."""
    if step == VENV_STEP:
        if phase.ok:
            copied = next((line for line in phase.log_tail.splitlines() if line.startswith("copiados ")), "")
            return "  entorno listo (Python 3.12)" + (f" · {copied}" if copied else "")
        if phase.code == 124:
            return "  no se pudo crear el entorno: copiar el repo o crear el entorno tardó más de 5 min"
        return "  no se pudo crear el entorno: " + _last_line(phase.log_tail, "sin detalle")
    if phase.code is None:
        return "  omitido: " + _last_line(phase.log_tail, "un paso anterior falló")
    if step == INSTALL_STEP:
        return "  dependencias instaladas" if phase.ok else "  ERROR al instalar: " + _last_line(phase.log_tail, f"código {phase.code}")
    if step == AUDIT_STEP:
        if out.audit is None:
            return "  pip-audit no devolvió resultado: " + _last_line(phase.log_tail, f"código {phase.code}")
        return f"  {len(parse_audit(out.audit))} paquete(s) vulnerable(s)"
    if step == PYTEST_STEP:
        if phase.code == 5:
            return "  no se encontraron pruebas"
        if out.junit is None:
            return f"  pytest no pudo correr (código {phase.code}): " + _last_line(phase.log_tail, "sin detalle")
        t = parse_junit(out.junit)
        return f"  {t.passed} passed, {t.failed} failed, {t.skipped} skipped"
    if step == COVERAGE_STEP:
        measured = [v for f, v in parse_coverage(out.coverage).items() if not _is_test(f) and not _is_tooling(f)]
        done, total = sum(c for c, _ in measured), sum(n for _, n in measured)
        return f"  líneas cubiertas: {round(100 * done / total, 1) if total else 0.0} %"
    return ""


def bandit_summary(findings: list[FindingInput]) -> str:
    bandit = [x for x in findings if x.tool == "Bandit"]
    return f"  {sum(x.sev == 'alta' for x in bandit)} alta · {sum(x.sev == 'media' for x in bandit)} media · {sum(x.sev == 'baja' for x in bandit)} baja"


def step_summary(step: int, r: PipelineResult) -> str | None:
    """Línea de resultado que muestra la terminal al terminar cada paso (índices de fake.JOB_STEPS)."""
    f = r.report.findings
    ruff = [x for x in f if x.tool == "Ruff"]
    sim = " (simulado)" if r.simulated else ""
    lines = {
        3: bandit_summary(f),
        4: "  sin sandbox: pip-audit no corrió (simulado)" if r.simulated else f"  {r.vulnerable} paquete(s) vulnerable(s)",
        5: f"  {r.passed} passed, {r.report.tests_failed} failed{sim}",
        6: f"  cobertura total: {r.report.coverage_total} %{sim}",
        7: f"  {len(ruff)} problema(s) ({sum(x.fix for x in ruff)} con corrección automática)",
        8: f"  complejidad media: {r.report.avg_complexity} · {len(r.report.complexity)} funciones",
        9: f"  score global: {r.score}",
    }
    return lines.get(step)
