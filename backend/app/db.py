import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
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

CREATE TABLE IF NOT EXISTS team_invites (
    code        TEXT PRIMARY KEY,
    team_id     TEXT NOT NULL REFERENCES teams (id) ON DELETE CASCADE,
    created_by  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

-- user_id = quien lo agregó; team_id = el equipo que lo ve (ver _migrate_teams para bases anteriores)
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

-- Jobs de análisis (app.analysis.jobs). `heartbeat` (time.time()) lo renueva el proceso que corre el job:
-- uno "running" sin latido reciente se interrumpió (reinicio del servidor). JSON en cat, options, logs, error, done.
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    team_id     TEXT NOT NULL,
    repo_id     TEXT NOT NULL,
    url         TEXT NOT NULL,
    name        TEXT NOT NULL,
    branch      TEXT NOT NULL,
    seed        INTEGER NOT NULL,
    cat         TEXT NOT NULL,
    options     TEXT NOT NULL,
    step        INTEGER NOT NULL DEFAULT 0,
    total       INTEGER NOT NULL,
    status      TEXT NOT NULL,
    logs        TEXT NOT NULL DEFAULT '[]',
    error       TEXT,
    commit_sha  TEXT,
    report_id   TEXT,
    done        TEXT,
    heartbeat   REAL NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_repo ON jobs (repo_id, status);

-- Intentos fallidos de contraseña de un enlace compartido (app.share), para frenar la fuerza bruta
CREATE TABLE IF NOT EXISTS share_failures (
    share_id    TEXT NOT NULL,
    at          REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS share_failures_share ON share_failures (share_id, at);

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

-- Equivalente de .ia_voy.toml; los valores son JSON
CREATE TABLE IF NOT EXISTS project_config (
    repo_id     TEXT PRIMARY KEY REFERENCES repos (id) ON DELETE CASCADE,
    weights     TEXT NOT NULL,
    thresholds  TEXT NOT NULL,
    ignored     TEXT NOT NULL,
    excluded    TEXT NOT NULL
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
    -- auto (Ruff, versión de pip-audit) | ia (la propone el LLM en el editor) | NULL; fix = 1 si hay alguna
    fix_kind   TEXT,
    status     TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    -- Texto de la línea señalada: permite reconocer el hallazgo aunque el archivo se mueva de lugar
    code       TEXT NOT NULL DEFAULT '',
    snippet    TEXT
);
CREATE INDEX IF NOT EXISTS findings_report ON findings (report_id, file);

-- Reglas de negocio del repo analizado (app.analyses.reglas, docs/adr/ADR-003). Van aparte de `findings`
-- (su CHECK solo admite seg/test/prac) y todavía no entran al score. Una fila por análisis que las revisó:
-- source NULL = el repo no declara reglas; error = el archivo no es válido (no hay resultados).
-- origin: repo | app (cargadas en Configuración); warnings: JSON (pruebas con reglas que no existen…);
-- tests_ran: 1 = las pruebas corrieron en el sandbox.
CREATE TABLE IF NOT EXISTS business_rule_checks (
    report_id   TEXT PRIMARY KEY REFERENCES reports (id) ON DELETE CASCADE,
    source      TEXT,
    project     TEXT,
    error       TEXT,
    origin      TEXT,
    warnings    TEXT NOT NULL DEFAULT '[]',
    tests_ran   INTEGER NOT NULL DEFAULT 0,
    -- El archivo del repo no era válido y se usaron las reglas corregidas en la app (origin = app)
    repo_error  TEXT
);

-- Una fila por regla. status: cumple | no_cumple | prueba_rota | no_implementada | sin_verificar | fuera_del_codigo; level: pruebas | patron | pruebas_y_patron | ninguno.
-- Sin CHECK en status/level para agregar niveles sin reconstruir la tabla. paths, evidence y tests son JSON.
CREATE TABLE IF NOT EXISTS business_rule_results (
    report_id       TEXT NOT NULL REFERENCES reports (id) ON DELETE CASCADE,
    rule_id         TEXT NOT NULL,
    pos             INTEGER NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    severity        TEXT NOT NULL,
    paths           TEXT NOT NULL DEFAULT '[]',
    forbidden       TEXT,
    required        TEXT,
    story           TEXT,
    owner           TEXT,
    criterion       TEXT,
    status          TEXT NOT NULL,
    level           TEXT NOT NULL,
    detail          TEXT NOT NULL,
    evidence        TEXT NOT NULL DEFAULT '[]',
    evidence_total  INTEGER NOT NULL DEFAULT 0,
    tests           TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (report_id, rule_id)
);

-- Reglas cargadas en la app (Configuración o Nuevo análisis; de apoyo, ADR-003): se usan si el repo no tiene su
-- reglas_negocio.toml o el suyo no es válido. Una por repo.
CREATE TABLE IF NOT EXISTS business_rules_upload (
    repo_id     TEXT PRIMARY KEY REFERENCES repos (id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    updated_by  TEXT
);

-- Arnés de las pruebas de reglas de negocio (app.projects.reglas_arnes, PROPUESTA_REGLAS_VERIFICABLES.md §7): uno
-- por repo. origin = ia | repo | manual. La prueba de humo y la aprobación valen para el código con ese hash.
CREATE TABLE IF NOT EXISTS business_rule_harness (
    repo_id        TEXT PRIMARY KEY REFERENCES repos (id) ON DELETE CASCADE,
    code           TEXT NOT NULL,
    origin         TEXT NOT NULL,
    source_path    TEXT,
    assumptions    TEXT NOT NULL DEFAULT '[]',
    model          TEXT,
    commit_sha     TEXT,
    smoke_status   TEXT NOT NULL DEFAULT 'pendiente',
    smoke_message  TEXT,
    smoke_tests    TEXT NOT NULL DEFAULT '[]',
    smoke_hash     TEXT,
    smoke_at       TEXT,
    approved_by    TEXT,
    approved_at    TEXT,
    approved_hash  TEXT,
    updated_at     TEXT NOT NULL,
    updated_by     TEXT
);

-- Pruebas de reglas generadas por IA voy (app.projects.reglas_pruebas, PROPUESTA_REGLAS_VERIFICABLES.md §6.3): una por
-- regla y repo. kind = prueba | no_implementada | fuera_del_codigo; origin = ia | manual. rule_hash = la versión de la
-- regla (si cambia, la prueba queda desactualizada). La corrida y la aprobación valen para el código con ese hash.
CREATE TABLE IF NOT EXISTS business_rule_tests (
    repo_id        TEXT NOT NULL REFERENCES repos (id) ON DELETE CASCADE,
    rule_id        TEXT NOT NULL,
    rule_hash      TEXT NOT NULL,
    kind           TEXT NOT NULL,
    tipo           TEXT NOT NULL,
    file           TEXT NOT NULL,
    code           TEXT NOT NULL,
    origin         TEXT NOT NULL,
    assumptions    TEXT NOT NULL DEFAULT '[]',
    endpoints      TEXT NOT NULL DEFAULT '[]',
    reason         TEXT,
    model          TEXT,
    run_status     TEXT NOT NULL DEFAULT 'pendiente',
    run_result     TEXT,
    run_hash       TEXT,
    run_at         TEXT,
    approved_by    TEXT,
    approved_at    TEXT,
    approved_hash  TEXT,
    updated_at     TEXT NOT NULL,
    updated_by     TEXT,
    -- Fase 5: matriz de permisos marcada por el equipo (JSON; origin = matriz) y prueba de fuerza (mutantes) del código
    -- con strength_hash
    matrix          TEXT,
    strength_status TEXT,
    strength_result TEXT,
    strength_hash   TEXT,
    strength_at     TEXT,
    PRIMARY KEY (repo_id, rule_id)
);

-- Evidencia de apoyo de una regla (app.projects.reglas_evidencia, PROPUESTA §8): dónde parece estar implementada, según
-- la IA. No cambia el estado ni el score. La última por regla; vale para la versión de la regla y el commit con que se pidió.
CREATE TABLE IF NOT EXISTS business_rule_evidence (
    repo_id     TEXT NOT NULL REFERENCES repos (id) ON DELETE CASCADE,
    rule_id     TEXT NOT NULL,
    rule_hash   TEXT NOT NULL,
    commit_sha  TEXT,
    data        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    created_by  TEXT,
    PRIMARY KEY (repo_id, rule_id)
);

-- Índice del asistente (app.assistant): fragmentos del código con su embedding (float32, normalizado)
CREATE TABLE IF NOT EXISTS code_chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id     TEXT NOT NULL REFERENCES repos (id) ON DELETE CASCADE,
    file        TEXT NOT NULL,
    start_line  INTEGER NOT NULL,
    end_line    INTEGER NOT NULL,
    text        TEXT NOT NULL,
    hash        TEXT NOT NULL,
    embedding   BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS code_chunks_repo ON code_chunks (repo_id, hash);

-- Enlaces públicos de un reporte (app.share). password_hash = "sal$hash" de scrypt, NULL = sin contraseña
CREATE TABLE IF NOT EXISTS shares (
    id            TEXT PRIMARY KEY,
    report_id     TEXT NOT NULL REFERENCES reports (id) ON DELETE CASCADE,
    user_id       TEXT NOT NULL,
    password_hash TEXT,
    expires_at    TEXT,
    include_code  INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

-- `state` de OAuth pendientes (app.github.states): un solo uso, vencen en 10 minutos
CREATE TABLE IF NOT EXISTS oauth_states (
    state       TEXT PRIMARY KEY,
    expires_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS repo_index (
    repo_id     TEXT PRIMARY KEY REFERENCES repos (id) ON DELETE CASCADE,
    files       INTEGER NOT NULL,
    py_files    INTEGER NOT NULL,
    readme      INTEGER NOT NULL,
    chunks      INTEGER NOT NULL,
    updated_at  TEXT NOT NULL
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
        # Fase 6: nota de las reglas de negocio (NULL = sin reglas medibles, o análisis anterior)
        "neg": "REAL",
    },
    # Sprint 8: nivel pruebas y reglas cargadas en la app
    "business_rule_checks": {
        "origin": "TEXT",
        "warnings": "TEXT NOT NULL DEFAULT '[]'",
        "tests_ran": "INTEGER NOT NULL DEFAULT 0",
        "repo_error": "TEXT",
    },
    "business_rule_results": {
        "tests": "TEXT NOT NULL DEFAULT '[]'",
    },
    # Correcciones con IA para lo que Ruff no corrige (Bandit, pruebas que fallan…); NULL = reportes anteriores
    "findings": {
        "fix_kind": "TEXT",
    },
    # Sprint 9, fase 5 de las reglas verificables: matriz de permisos y prueba de fuerza
    "business_rule_tests": {
        "matrix": "TEXT",
        "strength_status": "TEXT",
        "strength_result": "TEXT",
        "strength_hash": "TEXT",
        "strength_at": "TEXT",
    },
}


def _migrate_teams(conn: sqlite3.Connection) -> None:
    """
    Bases anteriores a los equipos: los repos eran de un usuario (UNIQUE user_id, name). Cada usuario
    recibe un equipo propio y la tabla repos se reconstruye con team_id (SQLite no cambia un UNIQUE).
    """
    if "team_id" in {row["name"] for row in conn.execute("PRAGMA table_info(repos)")}:
        return
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    for user in conn.execute("SELECT id, name FROM users WHERE id NOT IN (SELECT user_id FROM team_members)").fetchall():
        team_id = f"t{secrets.token_hex(6)}"
        conn.execute("INSERT INTO teams (id, name, created_at) VALUES (?, ?, ?)", (team_id, f"Equipo de {user['name']}", now))
        conn.execute("INSERT INTO team_members (user_id, team_id, role, joined_at) VALUES (?, ?, 'owner', ?)", (user["id"], team_id, now))
    conn.commit()
    # Procedimiento de SQLite para cambiar una tabla: nueva → copiar → borrar la vieja → renombrar.
    # Sin claves foráneas mientras tanto (reports, findings… apuntan a repos y no deben borrarse en cascada).
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(
        """
        BEGIN;
        CREATE TABLE repos_con_equipo (
            id TEXT PRIMARY KEY, team_id TEXT NOT NULL, user_id TEXT NOT NULL, name TEXT NOT NULL, url TEXT NOT NULL,
            branch TEXT NOT NULL, files INTEGER NOT NULL, status TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL,
            UNIQUE (team_id, name)
        );
        INSERT INTO repos_con_equipo (id, team_id, user_id, name, url, branch, files, status, error, created_at)
            SELECT r.id, COALESCE(m.team_id, 't-' || r.user_id), r.user_id, r.name, r.url, r.branch, r.files, r.status, r.error, r.created_at
            FROM repos r LEFT JOIN team_members m ON m.user_id = r.user_id;
        DROP TABLE repos;
        ALTER TABLE repos_con_equipo RENAME TO repos;
        COMMIT;
        """
    )
    conn.execute("PRAGMA foreign_keys = ON")


def _migrate(conn: sqlite3.Connection) -> None:
    for table, columns in MIGRATIONS.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
    _migrate_teams(conn)
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
