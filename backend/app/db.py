import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import Depends

from app.config import Settings, get_settings

# Modelo de datos inicial. Los hallazgos usan las mismas categorías y severidades del contrato
# (app/analyses/models.py y docs/FRONTEND_SPEC.md §4).
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    login       TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS repos (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    url         TEXT NOT NULL,
    branch      TEXT NOT NULL,
    files       INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL CHECK (status IN ('listo', 'analizando', 'error')),
    error       TEXT,
    created_at  TEXT NOT NULL,
    UNIQUE (user_id, name)
);

CREATE TABLE IF NOT EXISTS reports (
    id          TEXT PRIMARY KEY,
    repo_id     TEXT NOT NULL REFERENCES repos (id) ON DELETE CASCADE,
    num         INTEGER NOT NULL,
    branch      TEXT NOT NULL,
    commit_sha  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    duration_s  INTEGER NOT NULL,
    seg         INTEGER NOT NULL,
    test        INTEGER NOT NULL,
    prac        INTEGER NOT NULL,
    UNIQUE (repo_id, num)
);

CREATE TABLE IF NOT EXISTS findings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id  TEXT NOT NULL REFERENCES reports (id) ON DELETE CASCADE,
    sev        TEXT NOT NULL CHECK (sev IN ('alta', 'media', 'baja')),
    cat        TEXT NOT NULL CHECK (cat IN ('seg', 'test', 'prac')),
    tool       TEXT NOT NULL,
    rule       TEXT NOT NULL,
    file       TEXT NOT NULL,
    line       INTEGER NOT NULL,
    msg        TEXT NOT NULL,
    why        TEXT NOT NULL,
    rec        TEXT NOT NULL,
    fix        INTEGER NOT NULL DEFAULT 0,
    status     TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved'))
);
CREATE INDEX IF NOT EXISTS findings_report ON findings (report_id, file);
"""


def connect(path: str) -> sqlite3.Connection:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def session(path: str) -> Iterator[sqlite3.Connection]:
    """Conexión de corta vida fuera de una petición: confirma y cierra."""
    conn = connect(path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def get_db(settings: Settings = Depends(get_settings)) -> Iterator[sqlite3.Connection]:
    conn = connect(settings.database_path)
    try:
        yield conn
    finally:
        conn.close()
