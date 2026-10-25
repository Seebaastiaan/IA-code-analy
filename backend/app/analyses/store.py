import json
import secrets
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.analyses.models import FindingInput
from app.errors import ApiError
from app.teams.store import team_id_of

if TYPE_CHECKING:  # workspace importa el clon; aquí solo se usa como tipo
    from app.analyses.workspace import Workspace

# Pesos y umbrales por defecto de .ia_voy.toml (el cálculo del score llega en el Sprint 6)
DEFAULT_WEIGHTS = {"seg": 50, "test": 30, "prac": 20}
DEFAULT_THRESHOLDS = {"score": 70, "cov": 60}


@dataclass
class ProjectConfig:
    weights: dict[str, float]
    thresholds: dict[str, float]
    ignored: list[str]
    excluded: list[str]


def default_config() -> ProjectConfig:
    # B101 (assert) de Bandit es ruido en las pruebas de pytest
    return ProjectConfig(weights=dict(DEFAULT_WEIGHTS), thresholds=dict(DEFAULT_THRESHOLDS), ignored=["B101"], excluded=["migrations/", "tests/fixtures/"])


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class AnalysisStore:
    """
    Repositorios del equipo, su configuración y los análisis guardados, en SQLite. El job de análisis
    escribe; la pantalla Repositorios y la Configuración leen.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ─── Repos ───

    def upsert_repo(self, user_id: str, name: str, url: str, branch: str) -> str:
        """Id del repo del equipo del usuario con ese nombre ("owner/repo"); lo crea si no existe."""
        team_id = team_id_of(self.conn, user_id)
        row = self.conn.execute("SELECT id FROM repos WHERE team_id = ? AND name = ? COLLATE NOCASE", (team_id, name)).fetchone()
        if row is not None:
            self.conn.execute("UPDATE repos SET url = ?, branch = ? WHERE id = ?", (url, branch, row["id"]))
            self.conn.commit()
            return row["id"]
        repo_id = f"r{secrets.token_hex(4)}"
        self.conn.execute(
            "INSERT INTO repos (id, team_id, user_id, name, url, branch, files, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 0, 'listo', ?)",
            (repo_id, team_id, user_id, name, url, branch, now_iso()),
        )
        self.conn.commit()
        return repo_id

    def repo(self, repo_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM repos WHERE id = ?", (repo_id,)).fetchone()

    def repos(self, user_id: str) -> list[sqlite3.Row]:
        """Repos del equipo del usuario."""
        return self.conn.execute("SELECT * FROM repos WHERE team_id = ? ORDER BY created_at DESC", (team_id_of(self.conn, user_id),)).fetchall()

    def set_repo_status(self, repo_id: str, status: str, error: str | None = None, files: int | None = None) -> None:
        self.conn.execute("UPDATE repos SET status = ?, error = ?, files = COALESCE(?, files) WHERE id = ?", (status, error, files, repo_id))
        self.conn.commit()

    # ─── Configuración (.ia_voy.toml) ───

    def has_config(self, repo_id: str) -> bool:
        return self.conn.execute("SELECT 1 FROM project_config WHERE repo_id = ?", (repo_id,)).fetchone() is not None

    def config(self, repo_id: str) -> ProjectConfig:
        row = self.conn.execute("SELECT * FROM project_config WHERE repo_id = ?", (repo_id,)).fetchone()
        if row is None:
            return default_config()
        return ProjectConfig(**{k: json.loads(row[k]) for k in ("weights", "thresholds", "ignored", "excluded")})

    def save_config(self, repo_id: str, cfg: ProjectConfig) -> None:
        values = {k: json.dumps(v) for k, v in asdict(cfg).items()}
        self.conn.execute(
            """INSERT INTO project_config (repo_id, weights, thresholds, ignored, excluded) VALUES (:repo_id, :weights, :thresholds, :ignored, :excluded)
               ON CONFLICT(repo_id) DO UPDATE SET weights = excluded.weights, thresholds = excluded.thresholds,
               ignored = excluded.ignored, excluded = excluded.excluded""",
            {"repo_id": repo_id, **values},
        )
        self.conn.commit()

    # ─── Análisis guardados (reportes) ───

    def save_report(
        self, repo_id: str, branch: str, commit: str, duration_s: float, languages: list[dict],
        findings: list[FindingInput] | None = None, workspace: "Workspace | None" = None, created_at: str | None = None,
    ) -> tuple[str, int]:
        """
        Guarda un análisis como el siguiente del repo y devuelve (id, número). En el Sprint 5 el análisis
        llega hasta pip-audit: se guardan rama, commit, duración, lenguajes y los hallazgos de Seguridad
        (Bandit y pip-audit) en la tabla findings. El score (columnas seg/test/prac) lo calcula el Sprint 6.
        """
        last = self.conn.execute("SELECT MAX(num) FROM reports WHERE repo_id = ?", (repo_id,)).fetchone()[0]
        num = (last or 0) + 1
        report_id = f"{repo_id}-{num}"
        self.conn.execute(
            """INSERT INTO reports (id, repo_id, num, branch, commit_sha, created_at, duration_s, seg, test, prac, seed, languages)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, ?)""",
            (report_id, repo_id, num, branch, commit, created_at or now_iso(), round(duration_s), json.dumps(languages)),
        )
        lines: dict[str, list[str]] = {}
        for f in findings or []:
            code = f.code if f.code is not None else _line_text(workspace, lines, f.file, f.line)
            self.conn.execute(
                """INSERT INTO findings (report_id, sev, cat, tool, rule, file, line, msg, why, rec, code)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (report_id, f.sev, f.cat, f.tool, f.rule, f.file, f.line, f.msg, f.why, f.rec, code),
            )
        self.conn.commit()
        return report_id, num

    def finding_counts(self, report_id: str, ignored: list[str]) -> dict[str, int]:
        """Hallazgos abiertos del análisis por severidad, sin las reglas que el proyecto ignora."""
        counts = {"alta": 0, "media": 0, "baja": 0}
        rows = self.conn.execute("SELECT sev, rule FROM findings WHERE report_id = ? AND status = 'open'", (report_id,)).fetchall()
        for row in rows:
            if row["rule"] not in ignored:
                counts[row["sev"]] += 1
        return counts

    def report(self, report_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()

    def latest_report(self, repo_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM reports WHERE repo_id = ? ORDER BY num DESC LIMIT 1", (repo_id,)).fetchone()

    def recent_reports(self, repo_id: str, limit: int) -> list[sqlite3.Row]:
        """Últimos `limit` análisis, del más reciente al más antiguo."""
        return self.conn.execute("SELECT * FROM reports WHERE repo_id = ? ORDER BY num DESC LIMIT ?", (repo_id, limit)).fetchall()


def _line_text(workspace: "Workspace | None", cache: dict[str, list[str]], path: str, line: int) -> str:
    """Texto de la línea señalada (permite reconocer el hallazgo aunque el archivo cambie de lugar)."""
    if workspace is None:
        return ""
    if path not in cache:
        try:
            cache[path] = workspace.read(path).splitlines()
        except ApiError:
            cache[path] = []
    rows = cache[path]
    return rows[line - 1].strip()[:500] if 0 < line <= len(rows) else ""
