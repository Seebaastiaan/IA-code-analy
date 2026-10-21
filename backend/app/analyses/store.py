import json
import secrets
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from app.analyses.models import FindingInput, ReportInput
from app.analyses.scoring import DEFAULT_THRESHOLDS, DEFAULT_WEIGHTS, category_scores, effective_coverage
from app.analyses.workspace import Workspace, is_excluded, snippet
from app.teams.store import team_id_of


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
    """Repos, reportes y hallazgos en SQLite. El job de análisis escribe; el reporte los lee."""

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

    # ─── Configuración ───

    def config(self, repo_id: str) -> ProjectConfig:
        """Pesos, umbrales, reglas ignoradas y rutas excluidas del proyecto (por ahora, los de fábrica)."""
        return default_config()

    # ─── Reportes ───

    def save_report(self, repo_id: str, data: ReportInput, workspace: Workspace | None = None) -> tuple[str, int]:
        """Guarda el resultado de un análisis como el reporte siguiente del repo. Devuelve (id, número)."""
        last = self.conn.execute("SELECT MAX(num) FROM reports WHERE repo_id = ?", (repo_id,)).fetchone()[0]
        num = (last or 0) + 1
        report_id = f"{repo_id}-{num}"
        # seg/test/prac quedan como foto del momento; el score que se muestra se recalcula al leer
        cfg = self.config(repo_id)
        ignored = set(cfg.ignored)
        cats = category_scores(
            ((f.cat, f.sev) for f in data.findings if f.rule not in ignored and not is_excluded(f.file, cfg.excluded)),
            effective_coverage(data.coverage_total, data.analyzers), data.tests_failed, data.code_lines,
        )
        self.conn.execute(
            """INSERT INTO reports (id, repo_id, num, branch, commit_sha, created_at, duration_s, seg, test, prac, seed,
               coverage_total, tests_failed, avg_complexity, coverage, complexity, analyzers, languages, code_lines)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                report_id, repo_id, num, data.branch, data.commit, data.created_at or now_iso(), round(data.duration_s),
                round(cats["seg"]), round(cats["test"]), round(cats["prac"]), data.seed,
                data.coverage_total, data.tests_failed, data.avg_complexity,
                json.dumps([asdict(c) for c in data.coverage]), json.dumps([asdict(c) for c in data.complexity]), json.dumps(data.analyzers), json.dumps(data.languages), data.code_lines,
            ),
        )
        self.add_findings(report_id, data.findings, workspace, commit=False)
        self.conn.commit()
        return report_id, num

    def add_findings(self, report_id: str, findings: list[FindingInput], workspace: Workspace | None = None, lines_by_file: dict[str, list[str] | None] | None = None, commit: bool = True) -> list[int]:
        """Inserta hallazgos con su fragmento de código (±2 líneas) tomado de la copia de trabajo."""
        cache = dict(lines_by_file or {})
        ids = []
        for f in findings:
            if f.file not in cache:
                cache[f.file] = workspace.read_lines(f.file) if workspace else None
            lines = cache[f.file]
            code = f.code if f.code is not None else (lines[f.line - 1].rstrip("\r") if lines and 1 <= f.line <= len(lines) else "")
            snip = snippet(lines, f.line)
            cur = self.conn.execute(
                """INSERT INTO findings (report_id, sev, cat, tool, rule, file, line, msg, why, rec, fix, code, snippet)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (report_id, f.sev, f.cat, f.tool, f.rule, f.file, f.line, f.msg, f.why, f.rec, int(f.fix), code, json.dumps(snip) if snip else None),
            )
            ids.append(cur.lastrowid)
        if commit:
            self.conn.commit()
        return ids

    def report(self, report_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()

    def latest_report(self, repo_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM reports WHERE repo_id = ? ORDER BY num DESC LIMIT 1", (repo_id,)).fetchone()

    def previous_report(self, repo_id: str, num: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM reports WHERE repo_id = ? AND num < ? ORDER BY num DESC LIMIT 1", (repo_id, num)).fetchone()

    def recent_reports(self, repo_id: str, limit: int) -> list[sqlite3.Row]:
        """Últimos `limit` reportes, del más antiguo al más reciente."""
        rows = self.conn.execute("SELECT * FROM reports WHERE repo_id = ? ORDER BY num DESC LIMIT ?", (repo_id, limit)).fetchall()
        return rows[::-1]

    # ─── Hallazgos ───

    def findings(self, report_id: str, file: str | None = None) -> list[sqlite3.Row]:
        if file is None:
            return self.conn.execute("SELECT * FROM findings WHERE report_id = ? ORDER BY id", (report_id,)).fetchall()
        return self.conn.execute("SELECT * FROM findings WHERE report_id = ? AND file = ? ORDER BY id", (report_id, file)).fetchall()
