"""
Bandit sobre el clon: busca patrones de riesgo de seguridad en el código Python.

Solo lee el código (no lo ejecuta), así que corre en el backend sin sandbox. pip-audit sí ejecuta código del
repo (instala sus dependencias): ese corre en el sandbox (app.analysis.sandbox). Ruff y Radon se agregan
aquí en el Sprint 6.
"""

import json
import subprocess
import sys
from pathlib import Path

from app.analyses.models import FindingInput

# Analizar un repo completo puede tardar
DIR_TIMEOUT_S = 300
BANDIT_SEV = {"HIGH": "alta", "MEDIUM": "media", "LOW": "baja"}
BANDIT_CONF = {"HIGH": "alta", "MEDIUM": "media", "LOW": "baja"}
# Carpetas que no se analizan aunque estén en el repo (entornos, dependencias, compilados)
BANDIT_EXCLUDE = ",".join(f"./{d}" for d in (".git", ".venv", "venv", "env", "node_modules", "build", "dist", "site-packages"))


class AnalyzerError(Exception):
    pass


def _run(args: list[str], cwd: Path, timeout: int = DIR_TIMEOUT_S) -> str:
    try:
        proc = subprocess.run([sys.executable, "-m", *args], check=False, capture_output=True, timeout=timeout, cwd=cwd)
    except subprocess.TimeoutExpired as exc:
        raise AnalyzerError(f"{args[0]} tardó más de {timeout} s") from exc
    # Bandit sale con código 1 cuando encuentra problemas: lo que importa es la salida JSON
    return proc.stdout.decode("utf-8", errors="replace")


def bandit_finding(path: str, r: dict) -> FindingInput:
    return FindingInput(
        sev=BANDIT_SEV.get(r["issue_severity"], "baja"), cat="seg", tool="Bandit", rule=r["test_id"], file=path, line=r["line_number"],
        msg=r["issue_text"],
        why=f"Bandit detecta un patrón de riesgo de seguridad (confianza {BANDIT_CONF.get(r['issue_confidence'], 'baja')}). Documentación: {r.get('more_info', '')}".strip(),
        rec="Revisa la documentación de la regla y elimina el patrón inseguro. Si es un falso positivo, ignora la regla en la configuración del proyecto.",
    )


def is_test_path(path: str) -> bool:
    """Archivo de pruebas (tests/, test_*.py, *_test.py)."""
    name = path.rsplit("/", 1)[-1]
    return path.startswith("tests/") or "/tests/" in path or name.startswith("test_") or name.endswith("_test.py")


def _relative(root: Path, filename: str) -> str:
    path = Path(filename)
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(root.resolve())
        except ValueError:
            return path.as_posix()
    return path.as_posix().removeprefix("./")


def bandit_findings_dir(root: Path, files: list[str]) -> list[FindingInput]:
    """Hallazgos de Bandit de todo el repo en una sola ejecución (solo los .py de `files`)."""
    py = {f for f in files if f.endswith(".py")}
    if not py:
        return []
    try:
        results = json.loads(_run(["bandit", "-r", ".", "-f", "json", "-q", "-x", BANDIT_EXCLUDE], root))["results"]
    except (json.JSONDecodeError, KeyError) as exc:
        raise AnalyzerError("Bandit no devolvió un resultado válido") from exc
    # Bandit no revisa las pruebas: asserts o contraseñas de ejemplo ahí no son riesgos reales
    return [bandit_finding(rel, r) for r in results if (rel := _relative(root, r["filename"])) in py and not is_test_path(rel)]
