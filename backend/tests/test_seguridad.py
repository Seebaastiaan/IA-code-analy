"""Analizadores de Seguridad del Sprint 5: Bandit (real, sobre archivos) y los hallazgos de pip-audit."""

from app.analyses.analyzers import bandit_findings_dir, is_test_path
from app.analyses.store import AnalysisStore
from app.analyses.workspace import Workspace
from app.analysis.pipeline import _package_line, audit_findings, bandit_summary
from app.analysis.sandbox import SandboxOutput
from app.db import session
from tests.test_analysis import URL, wait_done
from tests.test_sandbox import AUDIT

INSEGURO = """import subprocess
import hashlib

PASSWORD = "super-secreto-123"


def correr(cmd):
    return subprocess.call(cmd, shell=True)


def huella(texto):
    return hashlib.md5(texto.encode()).hexdigest()
"""


def test_bandit_detecta_patrones_inseguros(tmp_path):
    (tmp_path / "app.py").write_text(INSEGURO, encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    found = bandit_findings_dir(tmp_path, ["app.py", "tests/test_app.py"])
    rules = {f.rule for f in found}
    assert {"B602", "B324", "B105"} <= rules
    assert all(f.file == "app.py" and f.cat == "seg" and f.tool == "Bandit" for f in found)
    # Las pruebas no se revisan (el assert de test_app.py no es un riesgo real)
    assert "B101" not in rules
    shell = next(f for f in found if f.rule == "B602")
    assert shell.sev == "alta" and shell.line == 8
    assert "alta" in bandit_summary(found)


def test_bandit_sin_python_no_corre(tmp_path):
    assert bandit_findings_dir(tmp_path, ["README.md"]) == []


def test_rutas_de_pruebas():
    assert is_test_path("tests/test_app.py") and is_test_path("pkg/test_util.py") and is_test_path("pkg/util_test.py")
    assert not is_test_path("app/testing_helpers.py")


def test_pip_audit_apunta_a_la_linea_del_paquete(settings):
    ws = Workspace(settings, "r1")
    ws.root.mkdir(parents=True)
    (ws.root / "requirements.txt").write_text("flask==3.0.0\nRequests==2.25.1\n", encoding="utf-8")
    [f] = audit_findings(ws, ["requirements.txt"], SandboxOutput(audit=AUDIT))
    assert (f.sev, f.cat, f.tool, f.rule, f.file, f.line) == ("alta", "seg", "pip-audit", "requests 2.25.1", "requirements.txt", 2)
    assert "PYSEC-1, GHSA-2" in f.msg and "requests 2.31.0" in f.rec
    # Dependencia indirecta (no está en requirements.txt): línea 1
    assert _package_line(["flask==3.0.0"], "urllib3") == 1


def test_conteo_respeta_reglas_ignoradas(client, settings):
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    with session(settings.database_path) as conn:
        conn.execute(
            "INSERT INTO findings (report_id, sev, cat, tool, rule, file, line, msg, why, rec) VALUES (?, 'baja', 'seg', 'Bandit', 'B101', 'main.py', 1, 'm', 'w', 'r')",
            (job["report_id"],),
        )
        store = AnalysisStore(conn)
        assert store.finding_counts(job["report_id"], []) == {"alta": 0, "media": 0, "baja": 1}
        assert store.finding_counts(job["report_id"], ["B101"]) == {"alta": 0, "media": 0, "baja": 0}
    # B101 está ignorada por defecto en la configuración del proyecto
    assert client.get(f"/api/repos/{job['repo_id']}/history").json()[0]["findings"]["baja"] == 0
