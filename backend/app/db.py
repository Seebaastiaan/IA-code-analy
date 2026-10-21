import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import Depends

from app.config import Settings, get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    github_id   INTEGER NOT NULL UNIQUE,
    login       TEXT NOT NULL,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL DEFAULT '',
    avatar_url  TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS github_accounts (
    user_id     TEXT PRIMARY KEY,
    login       TEXT NOT NULL,
    avatar_url  TEXT,
    token_enc   TEXT NOT NULL,
    scopes      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Equipos (app.teams): cada usuario pertenece a uno; los repos son del equipo
CREATE TABLE IF NOT EXISTS teams (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS team_members (
    user_id     TEXT PRIMARY KEY,
    team_id     TEXT NOT NULL REFERENCES teams (id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('owner', 'member')),
    joined_at   TEXT NOT NULL
);

-- user_id = quien lo agregó; team_id = el equipo que lo ve
CREATE TABLE IF NOT EXISTS repos (
    id          TEXT PRIMARY KEY,
    team_id     TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    name        TEXT NOT NULL,
    url         TEXT NOT NULL,
    branch      TEXT NOT NULL,
    files       INTEGER NOT NULL,
    status      TEXT NOT NULL,
    error       TEXT,
    created_at  TEXT NOT NULL,
    UNIQUE (team_id, name)
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
    seed        INTEGER NOT NULL,
    -- Resultado de los analizadores (app.analyses). coverage_total = -1: reporte anterior a los
    -- analizadores reales; su score sale de seg/test/prac guardados.
    coverage_total  REAL NOT NULL DEFAULT -1,
    tests_failed    INTEGER NOT NULL DEFAULT 0,
    avg_complexity  REAL NOT NULL DEFAULT 0,
    coverage        TEXT NOT NULL DEFAULT '[]',
    complexity      TEXT NOT NULL DEFAULT '[]',
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
    status     TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    -- Texto de la línea señalada: permite reconocer el hallazgo aunque el archivo se mueva de lugar
    code       TEXT NOT NULL DEFAULT '',
    snippet    TEXT
);
CREATE INDEX IF NOT EXISTS findings_report ON findings (report_id, file);

-- `state` de OAuth pendientes (app.github.states): un solo uso, vencen en 10 minutos
CREATE TABLE IF NOT EXISTS oauth_states (
    state       TEXT PRIMARY KEY,
    expires_at  REAL NOT NULL
);
"""

# Columnas agregadas después de crear la tabla: se añaden a las bases de datos existentes
MIGRATIONS = {
    "reports": {
        "coverage_total": "REAL NOT NULL DEFAULT -1",
        "tests_failed": "INTEGER NOT NULL DEFAULT 0",
        "avg_complexity": "REAL NOT NULL DEFAULT 0",
        "coverage": "TEXT NOT NULL DEFAULT '[]'",
        "complexity": "TEXT NOT NULL DEFAULT '[]'",
        # Analizadores que corrieron (JSON); vacío = todos (reportes anteriores a poder elegirlos)
        "analyzers": "TEXT NOT NULL DEFAULT '[]'",
        # Lenguajes del repo al analizarlo (JSON [{name, files}]); vacío = reportes anteriores
        "languages": "TEXT NOT NULL DEFAULT '[]'",
        # Líneas de Python analizadas (escala del score); 0 = reportes anteriores, sin escalar
        "code_lines": "INTEGER NOT NULL DEFAULT 0",
    },
}


def _migrate(conn: sqlite3.Connection) -> None:
    for table, columns in MIGRATIONS.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
    conn.execute("CREATE INDEX IF NOT EXISTS repos_team ON repos (team_id)")
    conn.commit()


def connect(path: str) -> sqlite3.Connection:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


@contextmanager
def session(path: str) -> Iterator[sqlite3.Connection]:
    """Conexión de corta vida fuera de una petición (jobs en segundo plano): confirma y cierra."""
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
