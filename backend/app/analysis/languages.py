"""
Lenguajes del repo clonado, por extensión. IA voy analiza solo Python: sirve para avisar cuando un repo
no tiene Python (el análisis se detiene con un mensaje claro) o cuando Python es una parte pequeña.
"""

import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

LANGUAGES = {
    ".py": "Python", ".pyi": "Python", ".ipynb": "Jupyter",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin", ".scala": "Scala",
    ".cs": "C#", ".c": "C", ".h": "C", ".cpp": "C++", ".cc": "C++", ".hpp": "C++",
    ".go": "Go", ".rs": "Rust", ".php": "PHP", ".rb": "Ruby", ".swift": "Swift", ".dart": "Dart",
    ".html": "HTML", ".css": "CSS", ".scss": "CSS", ".vue": "Vue", ".svelte": "Svelte",
    ".sh": "Shell", ".ps1": "PowerShell", ".sql": "SQL", ".r": "R", ".m": "MATLAB/Objective-C",
}
SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "env", "__pycache__", "site-packages", "dist", "build", "vendor"}
# No son "código" para decidir si Python es minoría (un proyecto web en Python también trae HTML y CSS)
MARKUP = {"HTML", "CSS", "SQL", "Shell", "PowerShell", "Jupyter"}
# Repos enormes: basta una muestra para saber qué lenguajes hay
MAX_FILES = 50_000


@dataclass
class Language:
    name: str
    files: int


def detect(root: Path) -> list[Language]:
    """Lenguajes con su número de archivos, de más a menos."""
    counts: Counter[str] = Counter()
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            seen += 1
            lang = LANGUAGES.get(os.path.splitext(name)[1].lower())
            if lang:
                counts[lang] += 1
        if seen >= MAX_FILES:
            break
    return [Language(name, n) for name, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def python_files(langs: list[Language]) -> int:
    return next((lang.files for lang in langs if lang.name == "Python"), 0)


def summary(langs: list[Language]) -> str:
    return " · ".join(f"{lang.name} {lang.files}" for lang in langs) or "ningún archivo de código reconocido"
