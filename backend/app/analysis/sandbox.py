"""
Pasos del análisis que EJECUTAN código del repo: crear el entorno (`uv venv`), instalar sus dependencias y
correr pip-audit sobre ellas (pasos 2, 3 y 5). Bandit solo lee el código y corre en el backend
(app.analyses.analyzers). pytest y coverage se agregan a este mismo script en el Sprint 6.

Un script bash (SCRIPT) corre en WSL2 o en Docker según `SANDBOX`:
- `wsl`: `wsl -d {SANDBOX_WSL_DISTRO} bash -l script.sh SRC OUT`. Aísla del entorno de Windows (variables,
  procesos) pero NO del disco. Pensado para repos propios.
- `docker`: contenedor desechable con el clon montado de solo lectura. Aislamiento real.
- `off`: sin sandbox; el entorno se crea en el backend con `python -m venv` (`local_venv`), fuera del clon.
  Las dependencias del repo NO se instalan en el backend (ejecutarían código ajeno), así que pip-audit no corre.

El script copia el clon a una carpeta temporal del sandbox (el clon no se toca) y deja en OUT un
`{fase}.code` (código de salida, o `skip`) y un `{fase}.log` por fase, más `audit.json`. El job espera cada
`.code` para avanzar la terminal en vivo (`SandboxRun.wait`).
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
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

from app.analysis.clone import clone_dir, clones_root, remove_tree
from app.config import Settings

log = logging.getLogger(__name__)

PHASES = ("venv", "install", "audit")
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
LOG_TAIL_LINES = 12
# Límite para crear el entorno local (SANDBOX=off)
LOCAL_VENV_TIMEOUT_S = 120

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

# Solo el código: sin .git, entornos, node_modules ni archivos de más de 5 MB
phase venv 300 bash -c '
  cd "$1" || exit 1
  find . \( -name .git -o -name node_modules -o -name .venv -o -name venv -o -name env -o -name __pycache__ \
            -o -name .mypy_cache -o -name .pytest_cache -o -name .tox -o -name dist -o -name build \) -prune \
         -o -type f -size -5M -print0 | tar --null -T - -cf - | tar -xf - -C "$2" || exit 1
  echo "copiados $(find "$2" -type f | wc -l) archivos"
  cd "$2" && uv venv -q .venv --python 3.12 && .venv/bin/python --version' _ "$SRC" "$WORK"
cd "$WORK" || { skip install audit; exit 0; }
if [ "$(cat "$OUT/venv.code")" != 0 ]; then skip install audit; exit 0; fi
export VIRTUAL_ENV="$WORK/.venv"; export PATH="$VIRTUAL_ENV/bin:$PATH"

phase install 600 bash -c '
  if [ -f requirements.txt ]; then uv pip install -r requirements.txt || exit $?
  elif [ -f pyproject.toml ] || [ -f setup.py ]; then uv pip install -e . || exit $?
  else echo "Sin requirements.txt ni pyproject.toml: no hay dependencias que instalar"
  fi'

# pip-audit revisa solo las dependencias instaladas del proyecto
SITE="$(echo "$VIRTUAL_ENV"/lib/python3*/site-packages)"
phase audit 300 env -u VIRTUAL_ENV uvx pip-audit --path "$SITE" -f json -o "$OUT/audit.json" --progress-spinner off
"""


@dataclass
class PhaseResult:
    name: str
    # Código de salida; None = no llegó a correr (una fase anterior falló, o el sandbox se cayó o se detuvo)
    code: int | None
    log_tail: str = ""

    @property
    def ok(self) -> bool:
        return self.code == 0


@dataclass
class SandboxOutput:
    phases: dict[str, PhaseResult] = field(default_factory=dict)
    audit: dict | None = None


def _tail(text: str) -> str:
    return "\n".join(text.strip().splitlines()[-LOG_TAIL_LINES:])


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
    """Un sandbox en marcha. `wait(fase)` espera a que esa fase termine."""

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
        tail = _tail(log_file.read_text(encoding="utf-8", errors="replace")) if log_file.is_file() else ""
        return PhaseResult(name, int(text) if text.lstrip("-").isdigit() else None, tail)

    async def wait(self, name: str) -> PhaseResult:
        while True:
            result = self._read(name)
            if result is not None:
                return result
            if self.proc.poll() is not None:
                # Terminó sin llegar a esta fase: lo que dijo el lanzador explica por qué
                launcher = (self.out / "launcher.log").read_text(encoding="utf-8", errors="replace").strip() if (self.out / "launcher.log").is_file() else ""
                return self._read(name) or PhaseResult(name, None, launcher[-600:] or "El sandbox terminó antes de esta fase")
            if time.monotonic() > self.deadline:
                self.stop()
                return PhaseResult(name, None, "Se agotó el tiempo del sandbox (SANDBOX_TIMEOUT_S)")
            await asyncio.sleep(0.3)

    def output(self) -> SandboxOutput:
        return SandboxOutput(
            phases={name: self._read(name) or PhaseResult(name, None) for name in PHASES},
            audit=_load_json(self.out / "audit.json"),
        )

    def _kill_inside(self) -> None:
        """Matar wsl.exe / docker CLI no detiene lo que corre dentro: se mata la sesión del script o el contenedor."""
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
    """(sandbox en marcha, None) o (None, motivo) si está apagado o no disponible: entonces se usa `local_venv`."""
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
    # Entorno mínimo: el sandbox no hereda las claves del backend (.env ya cargado en os.environ)
    env = {k: v for k, v in os.environ.items() if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "LOCALAPPDATA", "PROGRAMDATA", "DOCKER_HOST"}}
    try:
        with open(out / "launcher.log", "wb") as launcher:
            proc = subprocess.Popen(_command(settings, clone_dir(settings, repo_id), out, name), stdin=subprocess.DEVNULL, stdout=launcher, stderr=subprocess.STDOUT, env=env, creationflags=_NO_WINDOW)
    except OSError as exc:
        shutil.rmtree(out, ignore_errors=True)
        return None, str(exc)
    return SandboxRun(settings, proc, out, name), None


def venv_dir(settings: Settings, repo_id: str) -> Path:
    """Entorno local del repo (SANDBOX=off): junto al clon, no dentro, para no mezclarlo con el código."""
    return clones_root(settings) / f"{repo_id}.venv"


def local_venv(settings: Settings, repo_id: str) -> PhaseResult:
    """Crea el entorno en el backend con el mismo Python que lo corre. No ejecuta nada del repo. Bloqueante."""
    target = venv_dir(settings, repo_id)
    remove_tree(target)
    cmd = [sys.executable, "-m", "venv", "--without-pip", str(target)]
    try:
        done = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=LOCAL_VENV_TIMEOUT_S, creationflags=_NO_WINDOW)
    except subprocess.TimeoutExpired:
        return PhaseResult("venv", 124, "crear el entorno tardó demasiado")
    except OSError as exc:
        return PhaseResult("venv", None, str(exc))
    out = done.stdout + done.stderr
    if done.returncode == 0:
        # Verifica que el intérprete del entorno arranca (y deja su versión en la terminal)
        python = target / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        try:
            check = subprocess.run([str(python), "--version"], check=False, capture_output=True, text=True, timeout=30, creationflags=_NO_WINDOW)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return PhaseResult("venv", 1, f"el entorno no arranca: {exc}")
        if check.returncode != 0:
            return PhaseResult("venv", check.returncode, _tail(check.stdout + check.stderr))
        out += check.stdout + check.stderr
    return PhaseResult("venv", done.returncode, _tail(out))


def _last_line(text: str, default: str) -> str:
    lines = text.strip().splitlines()
    return lines[-1] if lines else default


def summary(phase: PhaseResult, where: str) -> str:
    """Línea de la terminal al terminar el paso 2."""
    if phase.ok:
        copied = next((line for line in phase.log_tail.splitlines() if line.startswith("copiados ")), "")
        python = next((line for line in phase.log_tail.splitlines() if line.startswith("Python ")), "")
        extra = " · ".join(x for x in (python, copied) if x)
        return f"  entorno listo en {where}" + (f" · {extra}" if extra else "")
    if phase.code == 124:
        return "  no se pudo crear el entorno: tardó más de lo permitido"
    return "  no se pudo crear el entorno: " + _last_line(phase.log_tail, "sin detalle")


def install_summary(phase: PhaseResult) -> str:
    """Línea de la terminal al terminar el paso 3 (no detiene el análisis: se reporta como hallazgo)."""
    if phase.ok:
        return "  " + _last_line(phase.log_tail, "dependencias instaladas")
    if phase.code is None:
        return "  no corrió: " + _last_line(phase.log_tail, "el sandbox se detuvo antes")
    reason = "tardó más de lo permitido" if phase.code == 124 else _last_line(phase.log_tail, f"código {phase.code}")
    return f"  ERROR al instalar: {reason}"


def audit_summary(phase: PhaseResult, out: SandboxOutput) -> str:
    """Línea de la terminal al terminar el paso 5."""
    if out.audit is None:
        return "  pip-audit no devolvió resultado: " + _last_line(phase.log_tail, f"código {phase.code}")
    return f"  {len(parse_audit(out.audit))} paquete(s) vulnerable(s)"


# ───────────────────────── Lectura de resultados ─────────────────────────


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
