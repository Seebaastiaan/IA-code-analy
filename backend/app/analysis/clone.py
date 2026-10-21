"""
Clonado REAL del repositorio (paso 1 del análisis). Los demás pasos siguen simulados.

El clon se guarda en `data/repos/{repo_id}` y se reemplaza en cada análisis. Para repos privados se usa
el token de GitHub del usuario como cabecera HTTP en variables de entorno de git: no queda escrito en
`.git/config` ni aparece en la línea de comandos.
"""

import base64
import os
import shutil
import stat
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings

CLONE_TIMEOUT_S = 180
MAX_TREE_FILES = 5000
MAX_FILE_BYTES = 1_000_000


@dataclass
class CloneError(Exception):
    title: str
    detail: str
    hint: str | None = None
    # Fallo de credenciales: vale la pena reintentar sin token (repo público con token revocado)
    auth: bool = False


@dataclass
class CloneResult:
    py_files: int
    seconds: float
    commit: str


def clones_root(settings: Settings) -> Path:
    """CLONES_PATH, o una carpeta local del usuario fuera del proyecto (que puede estar en OneDrive)."""
    if settings.clones_path:
        return Path(settings.clones_path)
    local = os.environ.get("LOCALAPPDATA")
    return Path(local) / "ia-voy" / "repos" if local else Path.home() / ".cache" / "ia-voy" / "repos"


def clone_dir(settings: Settings, repo_id: str) -> Path:
    return clones_root(settings) / repo_id


def _force_remove(func, path, _exc) -> None:
    # Git marca como solo lectura los objetos de .git; en Windows rmtree falla sin esto
    os.chmod(path, stat.S_IWRITE)
    func(path)


def remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, onexc=_force_remove)


def _git_env(token: str | None) -> dict[str, str]:
    config = [
        ("core.symlinks", "false"),  # los symlinks del repo quedan como archivos de texto: no apuntan fuera del clon
        ("credential.helper", ""),  # sin Git Credential Manager: nunca abre ventanas pidiendo usuario
        ("core.longpaths", "true"),  # Windows: rutas de más de 260 caracteres (node_modules subido al repo)
    ]
    if token:
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        config.append(("http.https://github.com/.extraheader", f"AUTHORIZATION: basic {basic}"))
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never", "GIT_LFS_SKIP_SMUDGE": "1", "GIT_CONFIG_COUNT": str(len(config))}
    for i, (key, value) in enumerate(config):
        env[f"GIT_CONFIG_KEY_{i}"] = key
        env[f"GIT_CONFIG_VALUE_{i}"] = value
    return env


def _explain(stderr: str, branch: str) -> CloneError:
    text = stderr.lower()
    last = next((line for line in reversed(stderr.strip().splitlines()) if line.strip()), "git clone falló")
    if "filename too long" in text or "checkout failed" in text or "invalid path" in text:
        detail = next((line for line in stderr.splitlines() if "too long" in line.lower() or "invalid path" in line.lower()), last)
        return CloneError(
            "No se pudieron escribir algunos archivos del repositorio",
            detail,
            "El repositorio tiene rutas demasiado largas o nombres que Windows no admite (suele pasar con node_modules subido a git).",
        )
    if "remote branch" in text and "not found" in text:
        return CloneError("La rama no existe", last, f'Revisa que la rama "{branch}" exista en el repositorio.')
    if any(s in text for s in ("repository not found", "could not read username", "authentication failed", "error: 403", "returned error: 401")):
        return CloneError(
            "Repositorio no encontrado o sin acceso",
            last,
            "Revisa la URL. Si es privado, entra con la cuenta de GitHub que tiene acceso.",
            auth=True,
        )
    if "could not resolve host" in text or "unable to access" in text:
        return CloneError("No se pudo conectar con GitHub", last, "Revisa la conexión a internet del servidor.")
    if any(s in text for s in TRANSIENT):
        return CloneError("Se cortó la conexión con GitHub durante el clonado", last, "Suele ser pasajero: vuelve a intentarlo.")
    return CloneError("No se pudo clonar el repositorio", last)


# Cortes de red o del servidor a mitad de la descarga: vale la pena reintentar una vez
TRANSIENT = ("aborted session", "early eof", "rpc failed", "connection reset", "connection was reset", "unexpected disconnect", "timed out", "operation timed out")


def _run_clone(url: str, branch: str, dest: Path, token: str | None) -> None:
    cmd = ["git", "clone", "--depth", "1", "--single-branch", "--no-tags", "--branch", branch, "--", url, str(dest)]
    for attempt in (1, 2):
        try:
            res = subprocess.run(
                cmd,
                check=False,
                env=_git_env(token),
                # Dentro de uvicorn (Windows) el stdin heredado puede ser inválido y tumbar a git-remote-https
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=CLONE_TIMEOUT_S,
            )
        except FileNotFoundError as exc:
            raise CloneError("Git no está instalado en el servidor", str(exc), "Instala Git y reinicia el backend.") from exc
        except subprocess.TimeoutExpired as exc:
            raise CloneError("El clonado tardó demasiado", f"Se canceló a los {CLONE_TIMEOUT_S} s", "Por ahora no se admiten repositorios muy grandes.") from exc
        if res.returncode == 0:
            return
        if attempt == 1 and any(s in res.stderr.lower() for s in TRANSIENT):
            remove_tree(dest)
            time.sleep(1)
            continue
        raise _explain(res.stderr, branch)


def clone(settings: Settings, repo_id: str, url: str, branch: str, token: str | None, attempt: str) -> CloneResult:
    """
    Clona en una carpeta temporal y solo después reemplaza el clon anterior, así un fallo no borra el
    último clon bueno. Bloqueante: se llama con asyncio.to_thread.
    """
    root = clones_root(settings)
    root.mkdir(parents=True, exist_ok=True)
    # Restos de intentos cancelados (best effort: alguno podría seguir en uso)
    for stale in root.glob(f"{repo_id}.tmp-*"):
        try:
            remove_tree(stale)
        except OSError:
            pass
    tmp = root / f"{repo_id}.tmp-{attempt}"
    start = time.monotonic()
    try:
        try:
            _run_clone(url, branch, tmp, token)
        except CloneError as exc:
            if not (exc.auth and token):
                raise
            # Con un token revocado GitHub rechaza incluso repos públicos: se reintenta sin él
            remove_tree(tmp)
            _run_clone(url, branch, tmp, None)
        count = len(python_files(tmp))
        head = subprocess.run(["git", "-C", str(tmp), "rev-parse", "--short=7", "HEAD"], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30, check=False)
    except BaseException:
        try:
            remove_tree(tmp)
        except OSError:
            pass
        raise
    return CloneResult(py_files=count, seconds=round(time.monotonic() - start, 1), commit=head.stdout.strip() or "0000000")


class Cloner:
    """Operaciones de clonado que usa el JobManager (las pruebas lo sustituyen para no usar la red)."""

    clone = staticmethod(clone)

    @staticmethod
    def promote(settings: Settings, repo_id: str, attempt: str) -> None:
        promote(settings, repo_id, attempt)


def promote(settings: Settings, repo_id: str, attempt: str) -> None:
    """
    Reemplaza el clon del repo por el recién descargado. En Windows, el antivirus o un sincronizador
    pueden retener unos segundos los archivos nuevos y el renombrado falla con "Access denied":
    se reintenta y, como último recurso, se copia.
    """
    tmp = clones_root(settings) / f"{repo_id}.tmp-{attempt}"
    dest = clone_dir(settings, repo_id)
    for wait in (0.2, 0.5, 1, 2, 3):
        try:
            remove_tree(dest)
            tmp.rename(dest)
            return
        except PermissionError:
            time.sleep(wait)
    remove_tree(dest)
    shutil.copytree(tmp, dest)
    try:
        remove_tree(tmp)
    except OSError:
        pass  # se limpia en el próximo clonado de este repo


def python_files(root: Path) -> list[str]:
    """Rutas relativas (con /) de los .py del clon, sin .git, ordenadas por carpeta y nombre."""
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        rel = Path(dirpath).relative_to(root)
        for name in sorted(filenames):
            if name.endswith(".py"):
                found.append((rel / name).as_posix())
                if len(found) >= MAX_TREE_FILES:
                    return found
    return found


def read_python_file(settings: Settings, repo_id: str, path: str) -> str:
    """Contenido de un .py del clon. Rechaza rutas que salgan del clon (../, absolutas)."""
    root = clone_dir(settings, repo_id).resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root) or target.suffix != ".py" or ".git" in target.relative_to(root).parts or not target.is_file():
        raise FileNotFoundError(path)
    if target.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(path)
    return target.read_text(encoding="utf-8", errors="replace")
