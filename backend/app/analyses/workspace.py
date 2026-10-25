"""
Copia de trabajo de un repo analizado: el clon de app.analysis.clone (`CLONES_PATH/{repo_id}/`). La crea
el job al clonar; la pantalla Archivos la lee (solo lectura). Toda ruta que llega del navegador pasa por `resolve`.
"""

import os
from pathlib import Path, PurePosixPath

from app.analysis.clone import clone_dir
from app.config import Settings
from app.errors import ApiError

MAX_FILE_BYTES = 1024 * 1024
MAX_TREE_ENTRIES = 2000
SKIP_DIRS = {"__pycache__", "node_modules", "venv", "env", "build", "dist", "site-packages"}
TEXT_EXTENSIONS = {".py", ".pyi", ".txt", ".toml", ".cfg", ".ini", ".md", ".rst", ".json", ".yaml", ".yml", ".sql", ".sh", ".html", ".css", ".js", ".ts"}
LANGUAGES = {
    ".py": "python", ".pyi": "python", ".toml": "ini", ".cfg": "ini", ".ini": "ini", ".md": "markdown", ".json": "json",
    ".yaml": "yaml", ".yml": "yaml", ".sql": "sql", ".sh": "shell", ".html": "html", ".css": "css", ".js": "javascript", ".ts": "typescript",
}


def language_of(path: str) -> str:
    return LANGUAGES.get(PurePosixPath(path).suffix.lower(), "plaintext")


def not_found(path: str) -> ApiError:
    return ApiError(404, "not_found", f"{path} no existe")


class Workspace:
    def __init__(self, settings: Settings, repo_id: str):
        self.settings = settings
        self.repo_id = repo_id
        self.root = clone_dir(settings, repo_id).resolve()

    def exists(self) -> bool:
        return self.root.is_dir()

    def resolve(self, path: str) -> Path:
        """Ruta absoluta de un archivo del repo; rechaza salir de la copia y las rutas ocultas (.git, .env…)."""
        rel = PurePosixPath(path)
        if not path or "\\" in path or rel.is_absolute() or any(part in ("", ".", "..") or part.startswith(".") for part in rel.parts):
            raise ApiError(400, "invalid_path", "Ruta de archivo no válida")
        full = (self.root / rel).resolve()
        # resolve() sigue enlaces simbólicos: un symlink que apunte fuera de la copia queda rechazado
        if not full.is_relative_to(self.root):
            raise ApiError(400, "invalid_path", "Ruta de archivo no válida")
        return full

    def read(self, path: str) -> str:
        full = self.resolve(path)
        if not full.is_file():
            raise not_found(path)
        if full.stat().st_size > MAX_FILE_BYTES:
            raise ApiError(413, "file_too_large", "El archivo es demasiado grande para mostrarlo (máx. 1 MB)")
        try:
            # newline="" conserva los saltos de línea tal cual (\r\n incluidos)
            with open(full, encoding="utf-8", newline="") as fh:
                return fh.read()
        except UnicodeDecodeError as exc:
            raise ApiError(415, "binary_file", "El archivo no es texto UTF-8") from exc

    def list_files(self, excluded: list[str]) -> list[str]:
        """Archivos de texto del repo (rutas posix), sin carpetas ocultas, entornos ni rutas excluidas."""
        if not self.exists():
            return []
        found: list[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d not in SKIP_DIRS)
            rel_dir = Path(dirpath).relative_to(self.root).as_posix()
            for name in sorted(filenames):
                rel = name if rel_dir == "." else f"{rel_dir}/{name}"
                if name.startswith(".") or PurePosixPath(name).suffix.lower() not in TEXT_EXTENSIONS:
                    continue
                if is_excluded(rel, excluded):
                    continue
                found.append(rel)
                if len(found) >= MAX_TREE_ENTRIES:
                    return found
        return found


def is_excluded(path: str, excluded: list[str]) -> bool:
    """Si `path` es una ruta excluida o está dentro de una carpeta excluida."""
    return any(path == e.strip("/") or path.startswith(e.strip("/") + "/") for e in excluded if e.strip("/"))

