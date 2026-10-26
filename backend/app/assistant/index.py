"""
Índice RAG del repo en SQLite (tablas code_chunks y repo_index).

`refresh` vuelve a fragmentar la copia de trabajo (rápido, local) y solo pide embeddings de los
fragmentos nuevos o cambiados (por hash). Así los cambios guardados desde el editor se reflejan en la
siguiente pregunta sin re-indexar todo ni gastar cuota de la API.
"""

import logging
import sqlite3
import threading
import time
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from app.analyses.store import AnalysisStore, now_iso
from app.analyses.workspace import Workspace
from app.assistant.chunker import INDEXED_SUFFIXES, Chunk, chunk_file
from app.assistant.llm import EMBED_DIM, LLM, LlmError
from app.config import Settings
from app.db import session

log = logging.getLogger(__name__)

MAX_CHUNKS = 3000
MAX_FILE_BYTES = 200_000

# Un solo refresco a la vez por repo (el job y una pregunta pueden coincidir)
_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)


@dataclass
class IndexStats:
    files: int
    py_files: int
    readme: bool
    chunks: int
    embedded: int  # fragmentos que se mandaron a embeddings en este refresco


@dataclass
class Hit:
    file: str
    start: int
    end: int
    text: str
    score: float


def _collect(settings: Settings, conn: sqlite3.Connection, repo_id: str) -> tuple[list[str], list[Chunk]]:
    ws = Workspace(settings, repo_id)
    excluded = AnalysisStore(conn).config(repo_id).excluded
    files = [f for f in ws.list_files(excluded) if f.endswith(INDEXED_SUFFIXES)]
    chunks: list[Chunk] = []
    for path in files:
        full = ws.resolve(path)
        if full.stat().st_size > MAX_FILE_BYTES:
            continue
        lines = ws.read_lines(path)
        if lines is not None:
            chunks.extend(chunk_file(path, "\n".join(lines)))
        if len(chunks) >= MAX_CHUNKS:
            break
    return files, chunks[:MAX_CHUNKS]


def refresh(settings: Settings, conn: sqlite3.Connection, llm: LLM, repo_id: str) -> IndexStats:
    """Sincroniza el índice con la copia de trabajo. Bloqueante (red): llamarlo desde un hilo."""
    with _locks[repo_id]:
        files, chunks = _collect(settings, conn, repo_id)
        stored: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for row in conn.execute("SELECT id, hash, file, start_line, end_line FROM code_chunks WHERE repo_id = ?", (repo_id,)):
            stored[row["hash"]].append(row)

        keep: set[int] = set()
        moved: list[tuple[int, int, int]] = []
        missing: list[Chunk] = []
        for c in chunks:
            rows = stored.get(c.hash)
            if rows:
                row = rows.pop()
                keep.add(row["id"])
                if (row["start_line"], row["end_line"]) != (c.start, c.end):
                    moved.append((c.start, c.end, row["id"]))
            else:
                missing.append(c)

        vectors = llm.embed([c.embed_text for c in missing]) if missing else np.zeros((0, EMBED_DIM), dtype=np.float32)
        stale = [r["id"] for rows in stored.values() for r in rows]
        conn.executemany("DELETE FROM code_chunks WHERE id = ?", [(i,) for i in stale])
        conn.executemany("UPDATE code_chunks SET start_line = ?, end_line = ? WHERE id = ?", moved)
        conn.executemany(
            "INSERT INTO code_chunks (repo_id, file, start_line, end_line, text, hash, embedding) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(repo_id, c.file, c.start, c.end, c.text, c.hash, v.astype(np.float32).tobytes()) for c, v in zip(missing, vectors, strict=True)],
        )
        stats = IndexStats(
            files=len(files),
            py_files=sum(f.endswith(".py") for f in files),
            readme=any(f.rsplit("/", 1)[-1].lower().startswith("readme") for f in files),
            chunks=len(chunks),
            embedded=len(missing),
        )
        conn.execute(
            """INSERT INTO repo_index (repo_id, files, py_files, readme, chunks, updated_at) VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(repo_id) DO UPDATE SET files = excluded.files, py_files = excluded.py_files, readme = excluded.readme,
               chunks = excluded.chunks, updated_at = excluded.updated_at""",
            (repo_id, stats.files, stats.py_files, int(stats.readme), stats.chunks, now_iso()),
        )
        conn.commit()
        return stats


def info(conn: sqlite3.Connection, repo_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM repo_index WHERE repo_id = ?", (repo_id,)).fetchone()


def search(conn: sqlite3.Connection, repo_id: str, query: np.ndarray, k: int = 6) -> list[Hit]:
    """Los `k` fragmentos más parecidos (similitud coseno; los vectores ya están normalizados)."""
    rows = conn.execute("SELECT file, start_line, end_line, text, embedding FROM code_chunks WHERE repo_id = ?", (repo_id,)).fetchall()
    if not rows:
        return []
    matrix = np.frombuffer(b"".join(r["embedding"] for r in rows), dtype=np.float32).reshape(len(rows), EMBED_DIM)
    scores = matrix @ query.astype(np.float32)
    best = np.argsort(-scores)[:k]
    return [Hit(rows[i]["file"], rows[i]["start_line"], rows[i]["end_line"], rows[i]["text"], float(scores[i])) for i in best]


# Indexaciones en segundo plano: el frontend consulta el estado cada 2 s mientras dice "building"; sin esto
# cada consulta lanzaba otra indexación completa en paralelo y, si fallaba (clave inválida, cuota), se
# quedaba en "building" para siempre gastando cuota.
RETRY_AFTER_S = 60
_state_lock = threading.Lock()
_building: set[str] = set()
_failed: dict[str, tuple[str, float]] = {}


def background_state(repo_id: str) -> tuple[bool, str | None]:
    """(indexando ahora, mensaje del último fallo si fue hace menos de RETRY_AFTER_S)."""
    with _state_lock:
        failure = _failed.get(repo_id)
        recent = failure is not None and time.monotonic() - failure[1] < RETRY_AFTER_S
        return repo_id in _building, failure[0] if recent else None


def start_background(repo_id: str) -> bool:
    """Marca el repo como "indexando". False si ya hay una indexación en curso o falló hace poco."""
    with _state_lock:
        failure = _failed.get(repo_id)
        if repo_id in _building or (failure and time.monotonic() - failure[1] < RETRY_AFTER_S):
            return False
        _building.add(repo_id)
        _failed.pop(repo_id, None)
        return True


def refresh_in_background(settings: Settings, repo_id: str) -> None:
    """Primera indexación al abrir el asistente (BackgroundTasks). Llamar solo si `start_background` dio True."""
    error: str | None = None
    try:
        with session(settings.database_path) as conn:
            refresh(settings, conn, LLM(settings), repo_id)
    except LlmError as exc:
        error = str(exc)
        log.warning("No se pudo indexar el repo %s: %s", repo_id, exc)
    except Exception:
        error = "Error inesperado al indexar"
        log.exception("No se pudo indexar el repo %s", repo_id)
    finally:
        with _state_lock:
            _building.discard(repo_id)
            if error:
                _failed[repo_id] = (error, time.monotonic())


def index_for_job(settings: Settings, repo_id: str) -> str:
    """Paso 10 del análisis. Nunca falla el job: devuelve la línea que se muestra en la terminal."""
    if not settings.gemini_api_key:
        return "  omitido: falta GEMINI_API_KEY (el asistente no está configurado)"
    try:
        with session(settings.database_path) as conn:
            stats = refresh(settings, conn, LLM(settings), repo_id)
    except LlmError as exc:
        return f"  no se pudo indexar: {exc} (se reintentará al abrir el asistente)"
    return f"  {stats.chunks} fragmentos de {stats.files} archivos ({stats.embedded} nuevos)"
