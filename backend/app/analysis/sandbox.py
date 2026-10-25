"""
Paso 2 del análisis: crear el entorno aislado (`uv venv`) donde, en los siguientes sprints, se instalarán
las dependencias y correrán pip-audit, pytest y coverage. En el Sprint 4 el sandbox solo crea el entorno.

Un script bash (SCRIPT) corre en WSL2 o en Docker según `SANDBOX`:
- `wsl`: `wsl -d {SANDBOX_WSL_DISTRO} bash -l script.sh SRC OUT`. Aísla del entorno de Windows (variables,
  procesos) pero NO del disco. Pensado para repos propios.
- `docker`: contenedor desechable con el clon montado de solo lectura. Aislamiento real.
- `off`: sin sandbox; el entorno se crea en el backend con `python -m venv` (`local_venv`), fuera del clon.

El script copia el clon a una carpeta temporal del sandbox (el clon no se toca) y deja en OUT `venv.code`
(código de salida) y `venv.log`. El job espera ese `.code` para avanzar la terminal en vivo.
"""

import asyncio
import logging
import os
import secrets
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from app.analysis.clone import clone_dir, clones_root, remove_tree
from app.config import Settings

log = logging.getLogger(__name__)

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
export UV_NO_PROGRESS=1
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Solo el código: sin .git, entornos, node_modules ni archivos de más de 5 MB
timeout --kill-after=10 300 bash -c '
  cd "$1" || exit 1
  find . \( -name .git -o -name node_modules -o -name .venv -o -name venv -o -name env -o -name __pycache__ \
            -o -name .mypy_cache -o -name .pytest_cache -o -name .tox -o -name dist -o -name build \) -prune \
         -o -type f -size -5M -print0 | tar --null -T - -cf - | tar -xf - -C "$2" || exit 1
  echo "copiados $(find "$2" -type f | wc -l) archivos"
  cd "$2" && uv venv -q .venv --python 3.12 && .venv/bin/python --version' _ "$SRC" "$WORK" > "$OUT/venv.log" 2>&1
echo $? > "$OUT/venv.code"
"""


@dataclass
class PhaseResult:
    name: str
    # Código de salida; None = no llegó a correr (el sandbox se cayó o se detuvo)
    code: int | None
    log_tail: str = ""

    @property
    def ok(self) -> bool:
        return self.code == 0


def _tail(text: str) -> str:
    return "\n".join(text.strip().splitlines()[-LOG_TAIL_LINES:])


def _wsl_path(path: Path) -> str:
    """C:\\Users\\ana\\x → /mnt/c/Users/ana/x (las unidades de Windows dentro de WSL)."""
    p = PureWindowsPath(path.resolve())
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
    """Un sandbox en marcha. `wait()` espera a que termine de crear el entorno."""

    def __init__(self, settings: Settings, proc: subprocess.Popen, out: Path, name: str = ""):
        self.settings = settings
        self.proc = proc
        self.out = out
        # Nombre del contenedor (Docker)
        self.name = name
        self.deadline = time.monotonic() + settings.sandbox_timeout_s

    def _read(self) -> PhaseResult | None:
        code_file = self.out / "venv.code"
        if not code_file.is_file():
            return None
        text = code_file.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            return None  # el script aún está escribiendo el archivo
        log_file = self.out / "venv.log"
        tail = _tail(log_file.read_text(encoding="utf-8", errors="replace")) if log_file.is_file() else ""
        return PhaseResult("venv", int(text) if text.lstrip("-").isdigit() else None, tail)

    async def wait(self) -> PhaseResult:
        while True:
            result = self._read()
            if result is not None:
                return result
            if self.proc.poll() is not None:
                # Terminó sin crear el entorno: lo que dijo el lanzador explica por qué
                launcher = (self.out / "launcher.log").read_text(encoding="utf-8", errors="replace").strip() if (self.out / "launcher.log").is_file() else ""
                return self._read() or PhaseResult("venv", None, launcher[-600:] or "El sandbox terminó antes de crear el entorno")
            if time.monotonic() > self.deadline:
                self.stop()
                return PhaseResult("venv", None, "Se agotó el tiempo del sandbox (SANDBOX_TIMEOUT_S)")
            await asyncio.sleep(0.3)

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


def summary(phase: PhaseResult, where: str) -> str:
    """Línea de la terminal al terminar el paso 2."""
    if phase.ok:
        copied = next((line for line in phase.log_tail.splitlines() if line.startswith("copiados ")), "")
        python = next((line for line in phase.log_tail.splitlines() if line.startswith("Python ")), "")
        extra = " · ".join(x for x in (python, copied) if x)
        return f"  entorno listo en {where}" + (f" · {extra}" if extra else "")
    if phase.code == 124:
        return "  no se pudo crear el entorno: tardó más de lo permitido"
    lines = phase.log_tail.strip().splitlines()
    return "  no se pudo crear el entorno: " + (lines[-1] if lines else "sin detalle")
