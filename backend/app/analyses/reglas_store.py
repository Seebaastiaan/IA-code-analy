"""
Reglas de negocio en la base de datos (docs/adr/ADR-003-reglas-de-negocio.md):
- resultados por análisis (`business_rule_checks`, `business_rule_results`), aparte de `findings`;
- reglas cargadas en la app (`business_rules_upload`), de apoyo: se usan si el repo no tiene el archivo o el suyo
  no es válido; un archivo válido del repo siempre gana.
"""

import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime

from app.analyses.reglas import RulesCheck


class RulesStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def save(self, report_id: str, check: RulesCheck, commit: bool = True) -> None:
        """Reemplaza lo guardado para el reporte."""
        self.conn.execute("DELETE FROM business_rule_results WHERE report_id = ?", (report_id,))
        self.conn.execute(
            """INSERT OR REPLACE INTO business_rule_checks (report_id, source, project, error, origin, warnings, tests_ran, repo_error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                report_id, check.source, check.project, check.error, check.origin, json.dumps(check.warnings, ensure_ascii=False),
                int(check.tests_ran), check.repo_error,
            ),
        )
        self.conn.executemany(
            """INSERT INTO business_rule_results (report_id, rule_id, pos, title, description, severity, paths, forbidden,
               required, story, owner, criterion, status, level, detail, evidence, evidence_total, tests)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    report_id, r.rule.id, pos, r.rule.title, r.rule.description, r.rule.severity, json.dumps(list(r.rule.paths)),
                    r.rule.forbidden, r.rule.required, r.rule.story, r.rule.owner, r.rule.criterion,
                    r.status, r.level, r.detail, json.dumps([asdict(e) for e in r.evidence], ensure_ascii=False), r.evidence_total,
                    json.dumps([asdict(t) for t in r.tests], ensure_ascii=False),
                )
                for pos, r in enumerate(check.results)
            ],
        )
        if commit:
            self.conn.commit()

    def check(self, report_id: str) -> sqlite3.Row | None:
        """None = el análisis es anterior a las reglas de negocio (no se revisaron)."""
        return self.conn.execute("SELECT * FROM business_rule_checks WHERE report_id = ?", (report_id,)).fetchone()

    def results(self, report_id: str) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM business_rule_results WHERE report_id = ? ORDER BY pos", (report_id,)).fetchall()

    # ─── Reglas cargadas en la app ───

    def upload(self, repo_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM business_rules_upload WHERE repo_id = ?", (repo_id,)).fetchone()

    def uploaded_text(self, repo_id: str) -> str | None:
        row = self.upload(repo_id)
        return row["content"] if row else None

    def save_upload(self, repo_id: str, content: str, user_id: str | None) -> sqlite3.Row:
        now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        self.conn.execute(
            "INSERT OR REPLACE INTO business_rules_upload (repo_id, content, updated_at, updated_by) VALUES (?, ?, ?, ?)",
            (repo_id, content, now, user_id),
        )
        self.conn.commit()
        return self.upload(repo_id)

    def delete_upload(self, repo_id: str) -> None:
        self.conn.execute("DELETE FROM business_rules_upload WHERE repo_id = ?", (repo_id,))
        self.conn.commit()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class HarnessStore:
    """Arnés de las pruebas de reglas de negocio (`business_rule_harness`, uno por repo)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get(self, repo_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM business_rule_harness WHERE repo_id = ?", (repo_id,)).fetchone()

    def save(
        self, repo_id: str, code: str, origin: str, user_id: str | None, *, source_path: str | None = None,
        assumptions: list[str] | None = None, model: str | None = None, commit_sha: str | None = None,
    ) -> None:
        """Código nuevo: la prueba de humo y la aprobación anteriores dejan de valer (son de otro código)."""
        self.conn.execute(
            """INSERT OR REPLACE INTO business_rule_harness (repo_id, code, origin, source_path, assumptions, model, commit_sha,
               smoke_status, smoke_message, smoke_tests, smoke_hash, smoke_at, approved_by, approved_at, approved_hash, updated_at, updated_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pendiente', NULL, '[]', NULL, NULL, NULL, NULL, NULL, ?, ?)""",
            (repo_id, code, origin, source_path, json.dumps(assumptions or [], ensure_ascii=False), model, commit_sha, _now(), user_id),
        )
        self.conn.commit()

    def edit(self, repo_id: str, code: str, user_id: str | None) -> None:
        """Edición a mano: conserva los supuestos y el modelo, pero vuelve a pedir la prueba de humo."""
        self.conn.execute(
            """UPDATE business_rule_harness SET code = ?, origin = CASE WHEN origin = 'repo' THEN 'repo' ELSE 'manual' END,
               smoke_status = 'pendiente', smoke_message = NULL, smoke_tests = '[]', smoke_hash = NULL, smoke_at = NULL,
               approved_by = NULL, approved_at = NULL, approved_hash = NULL, updated_at = ?, updated_by = ? WHERE repo_id = ?""",
            (code, _now(), user_id, repo_id),
        )
        self.conn.commit()

    def running(self, repo_id: str, code_hash: str) -> None:
        self.conn.execute(
            "UPDATE business_rule_harness SET smoke_status = 'corriendo', smoke_message = NULL, smoke_tests = '[]', smoke_hash = ?, smoke_at = ? WHERE repo_id = ?",
            (code_hash, _now(), repo_id),
        )
        self.conn.commit()

    def save_smoke(self, repo_id: str, code_hash: str, status: str, message: str, tests: list[dict]) -> None:
        """Solo si el arnés sigue siendo el que se probó (si lo editaron mientras corría, el resultado se descarta)."""
        self.conn.execute(
            """UPDATE business_rule_harness SET smoke_status = ?, smoke_message = ?, smoke_tests = ?, smoke_at = ?
               WHERE repo_id = ? AND smoke_hash = ?""",
            (status, message, json.dumps(tests, ensure_ascii=False), _now(), repo_id, code_hash),
        )
        self.conn.commit()

    def approve(self, repo_id: str, code_hash: str, user_id: str | None) -> None:
        self.conn.execute(
            "UPDATE business_rule_harness SET approved_by = ?, approved_at = ?, approved_hash = ? WHERE repo_id = ?",
            (user_id, _now(), code_hash, repo_id),
        )
        self.conn.commit()

    def delete(self, repo_id: str) -> None:
        self.conn.execute("DELETE FROM business_rule_harness WHERE repo_id = ?", (repo_id,))
        self.conn.commit()
