"""
Reglas de negocio en la base de datos (docs/adr/ADR-003-reglas-de-negocio.md):
- resultados por análisis (`business_rule_checks`, `business_rule_results`), aparte de `findings`;
- reglas cargadas desde Configuración (`business_rules_upload`), de apoyo: el archivo del repo siempre gana.
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
            """INSERT OR REPLACE INTO business_rule_checks (report_id, source, project, error, origin, warnings, tests_ran)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (report_id, check.source, check.project, check.error, check.origin, json.dumps(check.warnings, ensure_ascii=False), int(check.tests_ran)),
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
