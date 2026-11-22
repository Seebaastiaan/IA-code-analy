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
from app.analyses.scoring import business_score


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
        # Nota de las reglas de negocio del reporte (None = ninguna medible); el score la lee de aquí
        self.conn.execute("UPDATE reports SET neg = ? WHERE id = ?", (business_score((r.status, r.rule.severity) for r in check.results), report_id))
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


    # ─── Respuestas a las dudas (memoria del proyecto) ───

    def answers(self, repo_id: str) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM business_rule_answers WHERE repo_id = ? ORDER BY answered_at", (repo_id,)).fetchall()

    def save_answer(self, repo_id: str, key: str, title: str, question: str, answer: str, user_id: str | None) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO business_rule_answers (repo_id, question_key, title, question, answer, answered_by, answered_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (repo_id, key, title, question, answer, user_id, _now()),
        )
        self.conn.commit()


    # ─── Casos de control ───

    def expected(self, repo_id: str) -> dict[str, str]:
        rows = self.conn.execute("SELECT rule_id, expected FROM business_rule_expected WHERE repo_id = ?", (repo_id,)).fetchall()
        return {r["rule_id"]: r["expected"] for r in rows}

    def set_expected(self, repo_id: str, rule_id: str, expected: str | None, user_id: str | None) -> None:
        """`None` quita el caso de control."""
        if expected is None:
            self.conn.execute("DELETE FROM business_rule_expected WHERE repo_id = ? AND rule_id = ?", (repo_id, rule_id))
        else:
            self.conn.execute(
                "INSERT OR REPLACE INTO business_rule_expected (repo_id, rule_id, expected, set_by, set_at) VALUES (?, ?, ?, ?, ?)",
                (repo_id, rule_id, expected, user_id, _now()),
            )
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


class RuleTestsStore:
    """Pruebas generadas de las reglas de negocio (`business_rule_tests`, una por regla y repo)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def all(self, repo_id: str) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM business_rule_tests WHERE repo_id = ? ORDER BY rule_id", (repo_id,)).fetchall()

    def get(self, repo_id: str, rule_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM business_rule_tests WHERE repo_id = ? AND rule_id = ?", (repo_id, rule_id)).fetchone()

    def save(
        self, repo_id: str, rule_id: str, rule_hash: str, *, kind: str, tipo: str, file: str, code: str, origin: str,
        user_id: str | None, assumptions: list[str] | None = None, endpoints: list[str] | None = None, reason: str | None = None,
        model: str | None = None, matrix: dict | None = None,
    ) -> None:
        """Prueba nueva (o regenerada): la corrida, la aprobación y la prueba de fuerza anteriores dejan de valer."""
        self.conn.execute(
            """INSERT OR REPLACE INTO business_rule_tests (repo_id, rule_id, rule_hash, kind, tipo, file, code, origin, assumptions,
               endpoints, reason, model, run_status, run_result, run_hash, run_at, approved_by, approved_at, approved_hash,
               updated_at, updated_by, matrix)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', NULL, NULL, NULL, NULL, NULL, NULL, ?, ?, ?)""",
            (
                repo_id, rule_id, rule_hash, kind, tipo, file, code, origin, json.dumps(assumptions or [], ensure_ascii=False),
                json.dumps(endpoints or [], ensure_ascii=False), reason, model, _now(), user_id,
                json.dumps(matrix, ensure_ascii=False) if matrix is not None else None,
            ),
        )
        self.conn.commit()

    def edit(self, repo_id: str, rule_id: str, code: str, user_id: str | None) -> None:
        """Edición a mano: es una prueba (aunque antes fuera «no implementada») y hay que volver a correrla."""
        self.conn.execute(
            """UPDATE business_rule_tests SET code = ?, kind = 'prueba', reason = NULL, origin = 'manual', run_status = 'pendiente',
               run_result = NULL, run_hash = NULL, run_at = NULL, approved_by = NULL, approved_at = NULL, approved_hash = NULL,
               updated_at = ?, updated_by = ? WHERE repo_id = ? AND rule_id = ?""",
            (code, _now(), user_id, repo_id, rule_id),
        )
        self.conn.commit()

    def running(self, repo_id: str, hashes: dict[str, str]) -> None:
        """`hashes` = regla → hash del código que se va a correr."""
        self.conn.executemany(
            "UPDATE business_rule_tests SET run_status = 'corriendo', run_result = NULL, run_hash = ?, run_at = ? WHERE repo_id = ? AND rule_id = ?",
            [(h, _now(), repo_id, rid) for rid, h in hashes.items()],
        )
        self.conn.commit()

    def save_run(self, repo_id: str, results: dict[str, tuple[str, dict]]) -> None:
        """`results` = regla → (hash del código que corrió, resultado). Se descarta si la editaron mientras corría."""
        self.conn.executemany(
            """UPDATE business_rule_tests SET run_status = 'hecho', run_result = ?, run_at = ?
               WHERE repo_id = ? AND rule_id = ? AND run_hash = ? AND run_status = 'corriendo'""",
            [(json.dumps(result, ensure_ascii=False), _now(), repo_id, rid, h) for rid, (h, result) in results.items()],
        )
        self.conn.commit()

    def reset_running(self, repo_id: str) -> None:
        """Si el backend se reinició a media corrida: lo que quedó corriendo vuelve a pendiente."""
        self.conn.execute("UPDATE business_rule_tests SET run_status = 'pendiente', run_hash = NULL WHERE repo_id = ? AND run_status = 'corriendo'", (repo_id,))
        self.conn.execute(
            "UPDATE business_rule_tests SET strength_status = NULL, strength_hash = NULL WHERE repo_id = ? AND strength_status = 'corriendo'", (repo_id,)
        )
        self.conn.commit()

    # ─── Prueba de fuerza (app.projects.reglas_fuerza) ───

    def strength_running(self, repo_id: str, hashes: dict[str, str]) -> None:
        """`hashes` = regla → hash del código de la prueba que se va a mutar."""
        self.conn.executemany(
            "UPDATE business_rule_tests SET strength_status = 'corriendo', strength_result = NULL, strength_hash = ?, strength_at = ? WHERE repo_id = ? AND rule_id = ?",
            [(h, _now(), repo_id, rid) for rid, h in hashes.items()],
        )
        self.conn.commit()

    def save_strength(self, repo_id: str, results: dict[str, tuple[str, dict]]) -> None:
        """`results` = regla → (hash de la prueba, resultado). Se descarta si la editaron mientras corría."""
        self.conn.executemany(
            """UPDATE business_rule_tests SET strength_status = 'hecho', strength_result = ?, strength_at = ?
               WHERE repo_id = ? AND rule_id = ? AND strength_hash = ? AND strength_status = 'corriendo'""",
            [(json.dumps(result, ensure_ascii=False), _now(), repo_id, rid, h) for rid, (h, result) in results.items()],
        )
        self.conn.commit()

    def approve(self, repo_id: str, rule_id: str, code_hash: str, user_id: str | None) -> None:
        self.conn.execute(
            "UPDATE business_rule_tests SET approved_by = ?, approved_at = ?, approved_hash = ? WHERE repo_id = ? AND rule_id = ?",
            (user_id, _now(), code_hash, repo_id, rule_id),
        )
        self.conn.commit()

    def delete(self, repo_id: str, rule_id: str) -> None:
        self.conn.execute("DELETE FROM business_rule_tests WHERE repo_id = ? AND rule_id = ?", (repo_id, rule_id))
        self.conn.commit()


class EvidenceStore:
    """Evidencia de apoyo por regla (`business_rule_evidence`, app.projects.reglas_evidencia): la última que se pidió."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def all(self, repo_id: str) -> dict[str, sqlite3.Row]:
        rows = self.conn.execute("SELECT * FROM business_rule_evidence WHERE repo_id = ?", (repo_id,)).fetchall()
        return {r["rule_id"]: r for r in rows}

    def get(self, repo_id: str, rule_id: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM business_rule_evidence WHERE repo_id = ? AND rule_id = ?", (repo_id, rule_id)).fetchone()

    def save(self, repo_id: str, rule_id: str, rule_hash: str, commit_sha: str | None, data: dict, user_id: str | None) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO business_rule_evidence (repo_id, rule_id, rule_hash, commit_sha, data, created_at, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (repo_id, rule_id, rule_hash, commit_sha, json.dumps(data, ensure_ascii=False), _now(), user_id),
        )
        self.conn.commit()
