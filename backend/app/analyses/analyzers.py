"""
Análisis estático con Ruff y Bandit (hallazgos) y Radon (complejidad), sobre el repo completo o un archivo.

Solo leen el código (no lo ejecutan), así que corren en el backend sin sandbox. Las pruebas, la
cobertura y pip-audit sí ejecutan código del repo: esas las corre el worker dentro del sandbox WSL2.
"""

import json
import subprocess
import sys
from pathlib import Path

from app.analyses.models import ComplexityInput, FindingInput
from app.analyses.scoring import grade

TIMEOUT_S = 60
# Analizar un repo completo puede tardar más que un archivo
DIR_TIMEOUT_S = 300
# Reglas por defecto de Ruff (E4, E7, E9, F) + bugbear, simplificaciones y comprensiones
RUFF_EXTEND = "B,SIM,C4"
BANDIT_SEV = {"HIGH": "alta", "MEDIUM": "media", "LOW": "baja"}
BANDIT_CONF = {"HIGH": "alta", "MEDIUM": "media", "LOW": "baja"}


class AnalyzerError(Exception):
    pass


def _run(args: list[str], stdin: str, cwd: Path | None, timeout: int = TIMEOUT_S) -> str:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", *args], check=False, input=stdin.encode(), capture_output=True, timeout=timeout, cwd=cwd if cwd and cwd.is_dir() else None,
        )
    except subprocess.TimeoutExpired as exc:
        raise AnalyzerError(f"{args[0]} tardó más de {timeout} s") from exc
    # Ruff y Bandit salen con código 1 cuando encuentran problemas: lo que importa es la salida JSON
    return proc.stdout.decode("utf-8", errors="replace")


RUFF_CONFIGS = ("ruff.toml", ".ruff.toml", "pyproject.toml")


def _ruff_config_args(root: Path | None) -> list[str]:
    """
    Usa la configuración de Ruff del propio repo si la tiene; si no, `--isolated` para que no se cuele
    la de una carpeta superior (el pyproject.toml del backend) ni la del usuario del servidor.
    """
    for name in RUFF_CONFIGS:
        cfg = root / name if root else None
        if cfg and cfg.is_file() and (name != "pyproject.toml" or "[tool.ruff" in cfg.read_text(encoding="utf-8", errors="replace")):
            return ["--config", str(cfg)]
    return ["--isolated"]


def ruff_raw(content: str, path: str, cwd: Path | None) -> list[dict]:
    """Diagnósticos de Ruff (con sus correcciones) para `content` como si fuera `path` dentro del repo."""
    args = ["ruff", "check", "--output-format", "json", "--no-cache", *_ruff_config_args(cwd), "--extend-select", RUFF_EXTEND, "--stdin-filename", path, "-"]
    out = _run(args, content, cwd)
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise AnalyzerError("Ruff no devolvió un resultado válido") from exc


def bandit_raw(content: str) -> list[dict]:
    out = _run(["bandit", "-f", "json", "-q", "-"], content, None)
    try:
        return json.loads(out)["results"]
    except (json.JSONDecodeError, KeyError) as exc:
        raise AnalyzerError("Bandit no devolvió un resultado válido") from exc


def _ruff_severity(code: str) -> str:
    if code.startswith(("E9", "F63", "F7", "F82")):
        return "alta"  # errores de sintaxis, nombres no definidos…
    if code.startswith(("F", "B")):
        return "media"
    return "baja"


def _safe_fix(diag: dict) -> dict | None:
    fix = diag.get("fix")
    return fix if fix and fix.get("applicability") == "safe" and fix.get("edits") else None


def ruff_finding(path: str, d: dict) -> FindingInput:
    fix = _safe_fix(d)
    return FindingInput(
        sev=_ruff_severity(d["code"] or ""), cat="prac", tool="Ruff", rule=d["code"] or "E999", file=path, line=d["location"]["row"],
        msg=d["message"],
        why=f"Regla {d.get('name') or d['code']} de Ruff: suele indicar un error latente o código difícil de mantener. Documentación: {d.get('url') or 'https://docs.astral.sh/ruff/rules/'}",
        rec=f"Corrección automática disponible: {fix['message']}." if fix and fix.get("message") else "Corrígelo siguiendo la documentación de la regla.",
        fix=fix is not None,
    )


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


def static_findings(content: str, path: str, cwd: Path | None) -> list[FindingInput]:
    """Hallazgos de Ruff y Bandit para un archivo .py (Bandit no revisa las pruebas: ver static_findings_dir)."""
    if not path.endswith(".py"):
        return []
    found = [ruff_finding(path, d) for d in ruff_raw(content, path, cwd)]
    if not is_test_path(path):
        found += [bandit_finding(path, r) for r in bandit_raw(content)]
    return found


# Carpetas que no se analizan aunque estén en el repo (entornos, dependencias, compilados)
BANDIT_EXCLUDE = ",".join(f"./{d}" for d in (".git", ".venv", "venv", "env", "node_modules", "build", "dist", "site-packages"))


def _relative(root: Path, filename: str) -> str:
    path = Path(filename)
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(root.resolve())
        except ValueError:
            return path.as_posix()
    return path.as_posix().removeprefix("./")


def static_findings_dir(root: Path, files: list[str], ruff_on: bool = True, bandit_on: bool = True) -> list[FindingInput]:
    """Hallazgos de Ruff y Bandit de todo el repo en una sola ejecución de cada uno (solo los .py de `files`)."""
    py = {f for f in files if f.endswith(".py")}
    if not py:
        return []
    try:
        ruff = json.loads(_run(["ruff", "check", "--output-format", "json", "--no-cache", *_ruff_config_args(root), "--extend-select", RUFF_EXTEND, "."], "", root, DIR_TIMEOUT_S) or "[]") if ruff_on else []
        bandit = json.loads(_run(["bandit", "-r", ".", "-f", "json", "-q", "-x", BANDIT_EXCLUDE], "", root, DIR_TIMEOUT_S))["results"] if bandit_on else []
    except (json.JSONDecodeError, KeyError) as exc:
        raise AnalyzerError("Ruff o Bandit no devolvieron un resultado válido") from exc
    found = [ruff_finding(rel, d) for d in ruff if (rel := _relative(root, d["filename"])) in py]
    # Bandit no revisa las pruebas: asserts, contraseñas de ejemplo o requests sin timeout ahí no son riesgos
    # reales y, en un proyecto con muchas pruebas, dejaban la seguridad en 0
    found += [bandit_finding(rel, r) for r in bandit if (rel := _relative(root, r["filename"])) in py and not is_test_path(rel)]
    return found


def complexity(root: Path, files: list[str]) -> list[ComplexityInput]:
    """Complejidad ciclomática por función (Radon) de los archivos .py indicados."""
    py = [f for f in files if f.endswith(".py")]
    if not py:
        return []
    # Radon recibe carpetas o archivos; con muchos archivos la línea de comandos de Windows se queda corta
    targets = py if len(py) <= 200 else ["."]
    try:
        proc = subprocess.run([sys.executable, "-m", "radon", "cc", "-j", *targets], check=False, stdin=subprocess.DEVNULL, capture_output=True, timeout=DIR_TIMEOUT_S, cwd=root)
        data = json.loads(proc.stdout.decode("utf-8", errors="replace") or "{}")
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise AnalyzerError("Radon no devolvió un resultado válido") from exc
    keep = set(py)
    result = []
    for file, blocks in data.items():
        rel = _relative(root, file)
        if not isinstance(blocks, list) or rel not in keep:  # Radon reporta errores de parseo como {"error": ...}
            continue
        for b in blocks:
            name = f"{b['classname']}.{b['name']}" if b.get("classname") else b["name"]
            result.append(ComplexityInput(fn=name, file=rel, cc=b["complexity"], grade=grade(b["complexity"])))
    return sorted(result, key=lambda c: -c.cc)
