"""
Resultados de las reglas de negocio por análisis (tablas `business_rule_checks` y `business_rule_results`).
Van aparte de `findings`: ver docs/adr/ADR-003-reglas-de-negocio.md.
"""

import json
import sqlite3
from dataclasses import asdict

from app.analyses.reglas import RulesCheck


class RulesStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def save(self, report_id: str, check: RulesCheck, commit: bool = True) -> None:
        """Reemplaza lo guardado para el reporte."""
        self.conn.execute("DELETE FROM business_rule_results WHERE report_id = ?", (report_id,))
        self.conn.execute(
            "INSERT OR REPLACE INTO business_rule_checks (report_id, source, project, error) VALUES (?, ?, ?, ?)",
            (report_id, check.source, check.project, check.error),
        )
        self.conn.executemany(
            """INSERT INTO business_rule_results (report_id, rule_id, pos, title, description, severity, paths, forbidden,
               required, story, owner, criterion, status, level, detail, evidence, evidence_total)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    report_id, r.rule.id, pos, r.rule.title, r.rule.description, r.rule.severity, json.dumps(list(r.rule.paths)),
                    r.rule.forbidden, r.rule.required, r.rule.story, r.rule.owner, r.rule.criterion,
                    r.status, r.level, r.detail, json.dumps([asdict(e) for e in r.evidence], ensure_ascii=False), r.evidence_total,
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
