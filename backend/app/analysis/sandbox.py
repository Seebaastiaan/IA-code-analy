"""
Sandbox de los pasos que EJECUTAN código del repo analizado: entorno `uv`, dependencias, pip-audit,
pytest y coverage (pasos 2, 3, 5, 6 y 7). Ruff, Bandit y Radon solo leen el código y corren en el backend.

Un solo script bash (SCRIPT) corre en WSL2 o en Docker según `SANDBOX`:
- `wsl`: `wsl -d {SANDBOX_WSL_DISTRO} bash -l script.sh SRC OUT`. Aísla del entorno de Windows (variables,
  procesos) pero NO del disco: el código analizado puede leer /mnt/c. Pensado para repos propios.
- `docker`: contenedor desechable con el clon montado de solo lectura. Aislamiento real: úsalo con repos ajenos.
- `off`: no se ejecuta nada; pipeline simula esos pasos (marcados "(simulado)").

El script copia el clon a una carpeta temporal del sandbox (el clon del editor no se toca) y deja en OUT un
`{fase}.code` (código de salida, o `skip`) y un `{fase}.log` por fase, más audit.json, junit.xml y
coverage.json. El job espera cada `.code` para avanzar la terminal en vivo (`SandboxRun.wait`).
"""

import asyncio
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

from app.analysis.clone import clone_dir, clones_root
from app.config import Settings

log = logging.getLogger(__name__)

PHASES = ("venv", "install", "audit", "tests", "coverage")
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
LOG_TAIL_LINES = 12

SCRIPT = r"""#!/usr/bin/env bash
# Sandbox de IA voy (app/analysis/sandbox.py). Uso: sandbox.sh SRC OUT
set -u
SRC="$1"; OUT="$2"
# Id de sesión (setsid): al detener el sandbox se matan todos sus procesos, no solo el lanzador de Windows
echo $$ > "$OUT/pid"
export PATH="$HOME/.local/bin:$PATH"
export PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1 UV_NO_PROGRESS=1
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# phase NOMBRE SEGUNDOS COMANDO...: corre la fase con límite de tiempo y deja su código y su log en OUT
phase() {
  local name="$1" secs="$2"; shift 2
  timeout --kill-after=10 "$secs" "$@" > "$OUT/$name.log" 2>&1
  echo $? > "$OUT/$name.code"
}
skip() { for p in "$@"; do echo skip > "$OUT/$p.code"; done; }

# Solo lo necesario para correr las pruebas: sin .git, entornos, node_modules ni archivos de más de 5 MB.
# Copiar todo desde /mnt/c (videos, datasets, el historial de git) tardaba más que el límite del sandbox.
phase venv 300 bash -c '
  cd "$1" || exit 1
  find . \( -name .git -o -name node_modules -o -name .venv -o -name venv -o -name env -o -name __pycache__ \
            -o -name .mypy_cache -o -name .pytest_cache -o -name .tox -o -name dist -o -name build \) -prune \
         -o -type f -size -5M -print0 | tar --null -T - -cf - | tar -xf - -C "$2" || exit 1
  echo "copiados $(find "$2" -type f | wc -l) archivos"
  cd "$2" && uv venv -q .venv --python 3.12' _ "$SRC" "$WORK"
cd "$WORK" || { skip install audit tests coverage; exit 0; }
if [ "$(cat "$OUT/venv.code")" != 0 ]; then skip install audit tests coverage; exit 0; fi
export VIRTUAL_ENV="$WORK/.venv"; export PATH="$VIRTUAL_ENV/bin:$PATH"

phase install 600 bash -c '
  if [ -f requirements.txt ]; then uv pip install -r requirements.txt || exit $?
  elif [ -f pyproject.toml ] || [ -f setup.py ]; then uv pip install -e . || exit $?
  else echo "Sin requirements.txt ni pyproject.toml: no hay dependencias que instalar"
  fi
  # Dependencias de las pruebas, si el proyecto las declara. Opcionales: si fallan, las pruebas corren igual.
  for f in requirements-dev.txt requirements_dev.txt requirements-test.txt requirements_test.txt requirements-tests.txt \
           test-requirements.txt dev-requirements.txt requirements/test.txt requirements/tests.txt requirements/dev.txt; do
    [ -f "$f" ] && { uv pip install -q -r "$f" || echo "aviso: no se pudo instalar $f"; }
  done
  if [ -f pyproject.toml ]; then
    for g in test tests testing dev; do
      grep -qE "^[[:space:]]*$g[[:space:]]*=" pyproject.toml || continue
      uv pip install -q --group "$g" 2>/dev/null || uv pip install -q -e ".[$g]" 2>/dev/null || true
    done
  fi
  exit 0'

# Solo las dependencias del proyecto: pytest y coverage se instalan después
SITE="$(echo "$VIRTUAL_ENV"/lib/python3*/site-packages)"
phase audit 300 env -u VIRTUAL_ENV uvx pip-audit --path "$SITE" -f json -o "$OUT/audit.json" --progress-spinner off

uv pip install -q pytest coverage > "$OUT/tools.log" 2>&1
phase tests 600 coverage run --source=. --omit='.venv/*' -m pytest -q --maxfail=50 -p no:cacheprovider \
  --junitxml="$OUT/junit.xml" -o junit_family=xunit1
phase coverage 120 coverage json -q -o "$OUT/coverage.json"
"""


@dataclass
class PhaseResult:
    name: str
    # Código de salida; None = la fase no corrió (una anterior falló o el sandbox se detuvo)
    code: int | None
    log_tail: str = ""

    @property
    def ok(self) -> bool:
        return self.code == 0


@dataclass
class SandboxOutput:
    phases: dict[str, PhaseResult] = field(default_factory=dict)
    audit: dict | None = None
    junit: str | None = None
    coverage: dict | None = None

    @property
    def usable(self) -> bool:
        """El entorno se creó: los resultados son del repo (si no, falló el sandbox mismo y se simula)."""
        venv = self.phases.get("venv")
        return venv is not None and venv.ok


def _read_launcher(path: Path) -> str:
    """Salida de wsl.exe / docker. wsl.exe escribe sus propios errores en UTF-16 (sin BOM) si no hay WSL_UTF8=1."""
    if not path.is_file():
        return ""
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16", errors="replace")
    elif data.count(b"\x00") > len(data) // 4:
        text = data.decode("utf-16-le", errors="replace")
    else:
        text = data.decode("utf-8", errors="replace")
    return text.replace("\x00", "").strip()


def _wsl_path(path: Path) -> str:
    """C:\\Users\\ana\\x → /mnt/c/Users/ana/x (las unidades de Windows dentro de WSL)."""
    # Una ruta que ya trae unidad se traduce tal cual (en Linux o macOS resolve() la volvería relativa al cwd)
    p = PureWindowsPath(path) if PureWindowsPath(path).drive else PureWindowsPath(path.resolve())
    if not p.drive:
        return path.resolve().as_posix()
    return f"/mnt/{p.drive.rstrip(':').lower()}/" + "/".join(p.parts[1:])


def _command(settings: Settings, src: Path, out: Path, name: str) -> list[str]:
    if settings.sandbox == "wsl":
        # setsid: el script queda como líder de una sesión nueva (ver SandboxRun.stop)
        return ["wsl.exe", "-d", settings.sandbox_wsl_distro, "--", "setsid", "--wait", "bash", "-l", f"{_wsl_path(out)}/sandbox.sh", _wsl_path(src), _wsl_path(out)]
    return [
        "docker", "run", "--rm", "--name", name, "--memory", "2g", "--cpus", "2", "--pids-limit", "512",
        "-v", f"{src.resolve()}:/src:ro", "-v", f"{out.resolve()}:/out",
        settings.sandbox_docker_image, "bash", "/out/sandbox.sh", "/src", "/out",
    ]


def _available(settings: Settings) -> str | None:
    """None si el sandbox configurado se puede usar; si no, el motivo."""
    exe = "wsl.exe" if settings.sandbox == "wsl" else "docker"
    if shutil.which(exe) is None:
        return f"no se encontró {exe}"
    if settings.sandbox == "docker":
        try:
            subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, check=True, timeout=15, creationflags=_NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            return "Docker no está corriendo"
    return None


class SandboxRun:
    """Un sandbox en marcha para un análisis. `wait(fase)` espera a que esa fase termine."""

    def __init__(self, settings: Settings, proc: subprocess.Popen, out: Path, name: str = ""):
        self.settings = settings
        self.proc = proc
        self.out = out
        # Nombre del contenedor (Docker)
        self.name = name
        self.deadline = time.monotonic() + settings.sandbox_timeout_s

    def _read(self, name: str) -> PhaseResult | None:
        code_file = self.out / f"{name}.code"
        if not code_file.is_file():
            return None
        text = code_file.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            return None  # el script aún está escribiendo el archivo
        log_file = self.out / f"{name}.log"
        tail = ""
        if log_file.is_file():
            tail = "\n".join(log_file.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-LOG_TAIL_LINES:])
        return PhaseResult(name, int(text) if text.lstrip("-").isdigit() else None, tail)

    async def wait(self, name: str) -> PhaseResult:
        while True:
            result = self._read(name)
            if result is not None:
                return result
            if self.proc.poll() is not None:
                # Terminó sin llegar a esta fase (se cayó o se detuvo antes): lo que dijo el lanzador explica por qué
                launcher = _read_launcher(self.out / "launcher.log")
                return self._read(name) or PhaseResult(name, None, launcher[-600:] or "El sandbox terminó antes de esta fase")
            if time.monotonic() > self.deadline:
                self.stop()
                return PhaseResult(name, None, "Se agotó el tiempo del sandbox (SANDBOX_TIMEOUT_S)")
            await asyncio.sleep(0.3)

    def output(self) -> SandboxOutput:
        phases = {name: self._read(name) or PhaseResult(name, None) for name in PHASES}
        return SandboxOutput(
            phases=phases,
            audit=_load_json(self.out / "audit.json"),
            junit=(self.out / "junit.xml").read_text(encoding="utf-8", errors="replace") if (self.out / "junit.xml").is_file() else None,
            coverage=_load_json(self.out / "coverage.json"),
        )

    def _kill_inside(self) -> None:
        """
        Matar el proceso de Windows (wsl.exe / docker CLI) no detiene lo que corre dentro del sandbox: una
        copia o unas pruebas seguirían vivas. WSL: se mata la sesión del script. Docker: el contenedor.
        """
        if self.settings.sandbox == "docker":
            cmd = ["docker", "kill", self.name]
        else:
            pid_file = self.out / "pid"
            pid = pid_file.read_text(encoding="utf-8").strip() if pid_file.is_file() else ""
            if not pid.isdigit():
                return
            cmd = ["wsl.exe", "-d", self.settings.sandbox_wsl_distro, "--", "pkill", "-KILL", "-s", pid]
        try:
            subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=20, check=False, creationflags=_NO_WINDOW)
        except (OSError, subprocess.SubprocessError) as exc:
            log.warning("No se pudo detener el sandbox por dentro: %s", exc)

    def stop(self) -> None:
        if self.proc.poll() is None:
            self._kill_inside()
            self.proc.kill()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                log.warning("El sandbox no terminó tras matarlo")

    def close(self) -> None:
        self.stop()
        shutil.rmtree(self.out, ignore_errors=True)


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def start(settings: Settings, repo_id: str) -> tuple[SandboxRun | None, str | None]:
    """(sandbox en marcha, None) o (None, motivo) si está apagado o no disponible: entonces se simula."""
    if settings.sandbox == "off":
        return None, None
    reason = _available(settings)
    if reason:
        return None, reason
    out = clones_root(settings) / f"{repo_id}.sandbox"
    name = f"ia-voy-{repo_id}-{secrets.token_hex(3)}"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    # newline="\n": bash no acepta los \r de Windows
    (out / "sandbox.sh").write_text(SCRIPT, encoding="utf-8", newline="\n")
    # Entorno mínimo: el código analizado no hereda las claves del backend (.env ya cargado en os.environ)
    env = {k: v for k, v in os.environ.items() if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "LOCALAPPDATA", "PROGRAMDATA", "DOCKER_HOST"}}
    # Que wsl.exe escriba sus errores (p. ej. distro no encontrada) en UTF-8 y no en UTF-16
    env["WSL_UTF8"] = "1"
    try:
        with open(out / "launcher.log", "wb") as launcher:
            proc = subprocess.Popen(_command(settings, clone_dir(settings, repo_id), out, name), stdin=subprocess.DEVNULL, stdout=launcher, stderr=subprocess.STDOUT, env=env, creationflags=_NO_WINDOW)
    except OSError as exc:
        shutil.rmtree(out, ignore_errors=True)
        return None, str(exc)
    return SandboxRun(settings, proc, out, name), None


# ───────────────────────── Lectura de resultados ─────────────────────────


@dataclass
class TestCase:
    name: str
    file: str
    line: int
    message: str
    kind: str  # "failure" | "error"


@dataclass
class TestRun:
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    failures: list[TestCase] = field(default_factory=list)


def parse_junit(xml: str | None) -> TestRun:
    run = TestRun()
    if not xml:
        return run
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return run
    for case in root.iter("testcase"):
        bad = case.find("failure")
        if bad is None:
            bad = case.find("error")
        if case.find("skipped") is not None:
            run.skipped += 1
        elif bad is not None:
            run.failed += 1
            # xunit1: `file` relativo y `line` desde 0
            file = (case.get("file") or "").replace("\\", "/")
            if not file:
                file = (case.get("classname") or "").replace(".", "/") + ".py"
            line = int(case.get("line") or -1) + 1
            message = (bad.get("message") or bad.text or "").strip().splitlines()
            run.failures.append(TestCase(case.get("name") or "?", file, max(line, 1), message[0][:300] if message else "", bad.tag))
        else:
            run.passed += 1
    return run


def parse_coverage(data: dict | None) -> dict[str, tuple[int, int]]:
    """{archivo: (líneas ejecutadas, sentencias)} del coverage.json."""
    files = (data or {}).get("files") or {}
    out = {}
    for path, info in files.items():
        summary = info.get("summary") or {}
        out[path.replace("\\", "/").removeprefix("./")] = (int(summary.get("covered_lines", 0)), int(summary.get("num_statements", 0)))
    return out


@dataclass
class Vulnerability:
    package: str
    version: str
    ids: list[str]
    fix_versions: list[str]
    description: str


def parse_audit(data: dict | None) -> list[Vulnerability]:
    vulns = []
    for dep in (data or {}).get("dependencies") or []:
        found = dep.get("vulns") or []
        if not found:
            continue
        ids = list(dict.fromkeys(v.get("id", "?") for v in found))
        fixes = sorted({f for v in found for f in v.get("fix_versions") or []}, key=_version_key)
        description = next((v.get("description") for v in found if v.get("description")), "") or ""
        vulns.append(Vulnerability(dep.get("name", "?"), dep.get("version", "?"), ids, fixes, description))
    return vulns


def _version_key(v: str) -> tuple:
    return tuple(int(p) if p.isdigit() else 0 for p in re.split(r"[.\-+]", v))
