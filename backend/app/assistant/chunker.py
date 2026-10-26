"""
Fragmentos del código para el índice. En Python se usa el `ast` de la librería estándar (en lugar de
tree-sitter): una función o clase por fragmento, y el código suelto del módulo en bloques. Los demás
archivos de texto (README, configuración…) se parten en ventanas de líneas.
"""

import ast
import hashlib
from dataclasses import dataclass

WINDOW = 60
OVERLAP = 10
MAX_CHUNK_LINES = 120
MAX_CHUNK_CHARS = 6000  # gemini-embedding-001 admite 2048 tokens por texto
INDEXED_SUFFIXES = (".py", ".md", ".rst", ".txt", ".toml", ".cfg", ".ini", ".yaml", ".yml")


@dataclass
class Chunk:
    file: str
    start: int  # 1-based, inclusivo
    end: int
    text: str

    @property
    def hash(self) -> str:
        # Sin números de línea: si el fragmento solo se movió, se reutiliza su embedding
        return hashlib.sha256(f"{self.file}\0{self.text}".encode()).hexdigest()

    @property
    def embed_text(self) -> str:
        return f"Archivo: {self.file} (líneas {self.start}-{self.end})\n{self.text}"[:MAX_CHUNK_CHARS]


def _window(file: str, lines: list[str], start: int, end: int) -> list[Chunk]:
    """Ventanas de WINDOW líneas (con solapamiento) entre start y end (1-based, inclusivos)."""
    chunks, i = [], start
    while i <= end:
        j = min(end, i + WINDOW - 1)
        # Sin líneas en blanco en los extremos: el rango citado es el del código real
        a, b = i, j
        while a <= b and not lines[a - 1].strip():
            a += 1
        while b >= a and not lines[b - 1].strip():
            b -= 1
        if a <= b:
            chunks.append(Chunk(file, a, b, "\n".join(lines[a - 1 : b])))
        if j == end:
            break
        i = j - OVERLAP + 1
    return chunks


def _node_start(node: ast.AST) -> int:
    decorators = getattr(node, "decorator_list", [])
    return min([node.lineno, *(d.lineno for d in decorators)])


def _python(file: str, lines: list[str], source: str) -> list[Chunk]:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return _window(file, lines, 1, len(lines))
    chunks: list[Chunk] = []
    loose_start = 1

    def flush_loose(until: int) -> None:
        if until >= loose_start:
            chunks.extend(_window(file, lines, loose_start, until))

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        start, end = _node_start(node), node.end_lineno or node.lineno
        flush_loose(start - 1)
        if end - start + 1 <= MAX_CHUNK_LINES:
            chunks.append(Chunk(file, start, end, "\n".join(lines[start - 1 : end])))
        elif isinstance(node, ast.ClassDef):
            # Clase grande: la cabecera y cada método por separado
            methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            first = _node_start(methods[0]) - 1 if methods else end
            chunks.extend(_window(file, lines, start, max(start, first)))
            for m in methods:
                m_start, m_end = _node_start(m), m.end_lineno or m.lineno
                chunks.extend(_window(file, lines, m_start, m_end) if m_end - m_start + 1 > MAX_CHUNK_LINES else [Chunk(file, m_start, m_end, "\n".join(lines[m_start - 1 : m_end]))])
        else:
            chunks.extend(_window(file, lines, start, end))
        loose_start = end + 1
    flush_loose(len(lines))
    return [c for c in chunks if c.text.strip()]


def chunk_file(file: str, source: str) -> list[Chunk]:
    lines = source.replace("\r\n", "\n").split("\n")
    if file.endswith(".py"):
        return _python(file, lines, "\n".join(lines))
    return _window(file, lines, 1, len(lines))
