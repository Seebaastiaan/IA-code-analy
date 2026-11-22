"""
Análisis estático de UN archivo con Ruff y Bandit, y correcciones automáticas de Ruff.

Solo leen el código (no lo ejecutan), así que corren en el backend sin sandbox. Las pruebas, la
cobertura y pip-audit sí ejecutan código del repo: esas las corre el worker dentro del sandbox WSL2.
"""

import difflib
import json
import subprocess
import sys
from pathlib import Path

from app.analyses.mensajes import bandit_message, ruff_message
from app.analyses.models import ComplexityInput, FindingInput
from app.analyses.remedies import bandit_remedy, ruff_remedy
from app.analyses.scoring import grade
from app.errors import ApiError

TIMEOUT_S = 60
# Analizar un repo completo puede tardar más que un archivo
DIR_TIMEOUT_S = 300
# Reglas de Ruff sin configuración del repo: las que eran por defecto (E4, E7, E9, F) + bugbear,
# simplificaciones y comprensiones. Se fijan con --select: desde Ruff 0.17 el conjunto por defecto trae ~400
# reglas (estilo, imports, copyright…) y el reporte se llenaba de ruido que no está en docs/ia/catalogo-reglas.md.
RUFF_SELECT = "E4,E7,E9,F,B,SIM,C4"
# Con la configuración del repo: la suya más estas
RUFF_EXTEND = "B,SIM,C4"
# Correcciones de Ruff que se ofrecen. "unsafe" puede cambiar el comportamiento en casos raros: el editor muestra
# el diff y la persona decide antes de guardar. "display-only" no se aplica.
FIX_APPLICABILITY = ("safe", "unsafe")
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
    Configuración y reglas de Ruff: la del propio repo (más RUFF_EXTEND) si la tiene; si no, `--isolated` (que no
    se cuele la de una carpeta superior ni la del usuario del servidor) con las reglas fijas de RUFF_SELECT.
    """
    # --no-fix siempre: si el repo trae `fix = true`, Ruff con stdin imprime el código corregido en vez del JSON
    # (y sobre la carpeta reescribiría los archivos del clon). Las correcciones se aplican aparte con fix_content.
    for name in RUFF_CONFIGS:
        cfg = root / name if root else None
        if cfg and cfg.is_file() and (name != "pyproject.toml" or "[tool.ruff" in cfg.read_text(encoding="utf-8", errors="replace")):
            return ["--config", str(cfg), "--extend-select", RUFF_EXTEND, "--no-fix"]
    return ["--isolated", "--select", RUFF_SELECT, "--no-fix"]


def ruff_raw(content: str, path: str, cwd: Path | None) -> list[dict]:
    """Diagnósticos de Ruff (con sus correcciones) para `content` como si fuera `path` dentro del repo."""
    args = ["ruff", "check", "--output-format", "json", "--no-cache", *_ruff_config_args(cwd), "--stdin-filename", path, "-"]
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


def _auto_fix(diag: dict) -> dict | None:
    """La corrección de Ruff del diagnóstico, si se puede aplicar (safe o unsafe, con ediciones)."""
    fix = diag.get("fix")
    return fix if fix and fix.get("applicability") in FIX_APPLICABILITY and fix.get("edits") else None


def ruff_finding(path: str, d: dict) -> FindingInput:
    """Hallazgo de Ruff con recomendación concreta. Sin corrección de Ruff, la propone la IA en el editor."""
    code = d["code"] or "E999"
    fix = _auto_fix(d)
    message = ruff_message(d["message"])
    why, rec = ruff_remedy(code, message)
    if fix and fix.get("message"):
        rec += f" Corrección automática: {fix['message']}."
    return FindingInput(
        sev=_ruff_severity(code), cat="prac", tool="Ruff", rule=code, file=path, line=d["location"]["row"],
        msg=message, why=why, rec=rec, fix=True, fix_kind="auto" if fix else "ia",
    )


def bandit_finding(path: str, r: dict) -> FindingInput:
    """Hallazgo de Bandit con recomendación concreta. Bandit no corrige: la corrección la propone la IA."""
    message = bandit_message(r["test_id"], r["issue_text"])
    why, rec = bandit_remedy(r["test_id"], message)
    conf = BANDIT_CONF.get(r["issue_confidence"], "baja")
    return FindingInput(
        sev=BANDIT_SEV.get(r["issue_severity"], "baja"), cat="seg", tool="Bandit", rule=r["test_id"], file=path, line=r["line_number"],
        msg=message, why=f"{why} (Bandit, confianza {conf})", rec=rec, fix=True, fix_kind="ia",
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
        ruff = json.loads(_run(["ruff", "check", "--output-format", "json", "--no-cache", *_ruff_config_args(root), "."], "", root, DIR_TIMEOUT_S) or "[]") if ruff_on else []
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


# ─── Correcciones automáticas ───


def _offsets(content: str) -> list[int]:
    """Desplazamiento de inicio de cada línea (1-based por índice + 1)."""
    starts, pos = [0], 0
    for line in content.split("\n"):
        pos += len(line) + 1
        starts.append(pos)
    return starts


def apply_edits(content: str, edits: list[dict]) -> str:
    """Aplica ediciones de Ruff ({location, end_location, content}, filas y columnas 1-based)."""
    starts = _offsets(content)

    def at(loc: dict) -> int:
        return min(starts[loc["row"] - 1] + loc["column"] - 1, len(content))

    spans = sorted(((at(e["location"]), at(e["end_location"]), e["content"]) for e in edits), reverse=True)
    out, last_start = content, len(content) + 1
    for start, end, text in spans:
        if end > last_start:  # se solapa con una edición ya aplicada: se omite
            continue
        out = out[:start] + text + out[end:]
        last_start = start
    return out


def diff_patches(path: str, old: str, new: str) -> list[dict]:
    """Expresa el cambio como parches de una línea (`Patch` del frontend): texto nuevo o None = borrar."""
    a, b = old.split("\n"), new.split("\n")
    replace: dict[int, list[str]] = {}
    prefix: dict[int, list[str]] = {}
    suffix: list[str] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            for k in range(i1, i2):
                replace[k] = []
            replace[i1] = b[j1:j2]
        elif tag == "insert":
            if i1 < len(a):
                prefix.setdefault(i1, []).extend(b[j1:j2])
            else:
                suffix.extend(b[j1:j2])
    if suffix and a:
        last = len(a) - 1
        replace[last] = replace.get(last, [a[last]]) + suffix
    patches = []
    for k in sorted(set(replace) | set(prefix)):
        lines = prefix.get(k, []) + replace.get(k, [a[k]])
        patches.append({"file": path, "line": k + 1, "original": a[k], "text": "\n".join(lines) if lines else None})
    return patches


def fix_content(content: str, path: str, cwd: Path | None, targets: list[tuple[str, str, int]]) -> str:
    """
    Aplica las correcciones de Ruff de los hallazgos `targets` = (regla, texto de la línea, línea).
    Cada hallazgo se ubica por regla y texto de su línea (o la más cercana), no solo por número de línea.
    """
    diags = [d for d in ruff_raw(content, path, cwd) if _auto_fix(d)]
    lines = content.split("\n")
    edits, used = [], set()
    for rule, code, line in targets:
        candidates = [
            (abs(d["location"]["row"] - line), i)
            for i, d in enumerate(diags)
            if i not in used and d["code"] == rule and (not code or lines[d["location"]["row"] - 1].rstrip("\r") == code)
        ]
        if not candidates:
            continue
        _, idx = min(candidates)
        used.add(idx)
        edits += diags[idx]["fix"]["edits"]
    if not edits:
        raise ApiError(409, "fix_unavailable", "La corrección ya no aplica: el código cambió o el hallazgo se resolvió")
    return apply_edits(content, edits)
