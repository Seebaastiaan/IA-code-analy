"""Analizadores de Seguridad: Bandit (real, sobre archivos) y los hallazgos de pip-audit."""

from app.analyses.analyzers import is_test_path, static_findings_dir
from app.analyses.workspace import Workspace
from app.analysis.pipeline import _package_line, audit_findings, bandit_summary
from app.analysis.sandbox import SandboxOutput
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
    found = static_findings_dir(tmp_path, ["app.py", "tests/test_app.py"], ruff_on=False)
    rules = {f.rule for f in found}
    assert {"B602", "B324", "B105"} <= rules
    assert all(f.file == "app.py" and f.cat == "seg" and f.tool == "Bandit" for f in found)
    # Las pruebas no se revisan (el assert de test_app.py no es un riesgo real)
    assert "B101" not in rules
    shell = next(f for f in found if f.rule == "B602")
    assert shell.sev == "alta" and shell.line == 8
    assert "alta" in bandit_summary(found)


def test_bandit_sin_python_no_corre(tmp_path):
    assert static_findings_dir(tmp_path, ["README.md"]) == []


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
