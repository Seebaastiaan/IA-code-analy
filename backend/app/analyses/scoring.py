"""
Score oficial (docs/FRONTEND_SPEC.md §1.3). Se calcula al leer, a partir de los hallazgos abiertos y no
ignorados, así que resolver un hallazgo en el editor, ignorar una regla o cambiar los pesos se refleja
de inmediato sin re-analizar.

- seg  = 100 − Σ penalización de los hallazgos de seguridad abiertos
- prac = 100 − Σ penalización de los hallazgos de buenas prácticas abiertos
  En proyectos de más de 1000 líneas de Python la penalización se escala por cada 1000 líneas: 60 avisos
  pesan igual que 6 en un proyecto de 1000 líneas (si no, cualquier proyecto grande quedaba en 0).
- test = cobertura total − 5 por cada prueba que falla (sin coverage elegido, la cobertura cuenta como 100)
- global = promedio ponderado con los pesos del proyecto
"""

from collections.abc import Iterable

PENALTY = {
    "seg": {"alta": 12, "media": 6, "baja": 2},
    "prac": {"alta": 6, "media": 3, "baja": 1},
}
FAILED_TEST_PENALTY = 5
# Tamaño de proyecto a partir del cual la penalización se escala (líneas de Python)
LINES_PER_UNIT = 1000
DEFAULT_WEIGHTS = {"seg": 50, "test": 30, "prac": 20}
DEFAULT_THRESHOLDS = {"score": 70, "cov": 60}


def _clamp(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def category_scores(open_findings: Iterable[tuple[str, str]], coverage_total: float, tests_failed: int, code_lines: int = 0) -> dict[str, float]:
    """
    `open_findings` = pares (categoría, severidad) de los hallazgos abiertos y no ignorados.
    `code_lines` = líneas de Python del proyecto (0 = desconocido: reportes anteriores, sin escalar).
    """
    penalty = {"seg": 0, "prac": 0}
    for cat, sev in open_findings:
        if cat in PENALTY:
            penalty[cat] += PENALTY[cat][sev]
    scale = min(1.0, LINES_PER_UNIT / code_lines) if code_lines else 1.0
    return {
        "seg": _clamp(100 - penalty["seg"] * scale),
        "test": _clamp(coverage_total - FAILED_TEST_PENALTY * tests_failed),
        "prac": _clamp(100 - penalty["prac"] * scale),
    }


def effective_coverage(coverage_total: float, analyzers: list[str] | tuple[str, ...]) -> float:
    """Cobertura que entra al score: si no se eligió coverage no se midió y no se descuenta nada por ella."""
    return coverage_total if not analyzers or "coverage" in analyzers else 100.0


def global_score(weights: dict[str, float], cats: dict[str, float]) -> float:
    total = sum(weights.values()) or 1
    return round(sum(weights[c] * cats[c] for c in ("seg", "test", "prac")) / total, 1)


def grade(cc: int) -> str:
    """Grado de complejidad ciclomática según Radon."""
    for limit, letter in ((5, "A"), (10, "B"), (20, "C"), (30, "D"), (40, "E")):
        if cc <= limit:
            return letter
    return "F"
