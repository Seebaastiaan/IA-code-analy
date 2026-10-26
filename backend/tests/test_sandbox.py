"""Sandbox de pytest, coverage y pip-audit (app.analysis.sandbox): lectura de resultados y el job con un sandbox falso."""

from pathlib import Path

import pytest

from app.analysis import sandbox
from app.analysis.sandbox import PHASES, PhaseResult, SandboxOutput, _wsl_path, parse_audit, parse_coverage, parse_junit
from tests.test_analysis import URL, wait_done

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="4" failures="1" errors="1" skipped="1">
  <testcase classname="tests.test_servicio" file="tests/test_servicio.py" line="3" name="test_suma" />
  <testcase classname="tests.test_servicio" file="tests/test_servicio.py" line="6" name="test_resta">
    <failure message="AssertionError: assert 1 == 2">def test_resta(): ...</failure>
  </testcase>
  <testcase classname="tests.test_servicio" file="tests/test_servicio.py" line="9" name="test_db">
    <error message="fixture 'db' not found" />
  </testcase>
  <testcase classname="tests.test_servicio" file="tests/test_servicio.py" line="12" name="test_lento">
    <skipped message="lento" />
  </testcase>
</testsuite></testsuites>"""

AUDIT = {
    "dependencies": [
        {"name": "requests", "version": "2.25.1", "vulns": [
            {"id": "PYSEC-1", "fix_versions": ["2.31.0"], "description": "Fuga de cabeceras"},
            {"id": "PYSEC-1", "fix_versions": ["2.31.0"]},
            {"id": "GHSA-2", "fix_versions": ["2.32.0"]},
        ]},
        {"name": "flask", "version": "3.0.0", "vulns": []},
    ],
}

COVERAGE = {"files": {
    "main.py": {"summary": {"covered_lines": 1, "num_statements": 1}},
    "app/core/servicio.py": {"summary": {"covered_lines": 1, "num_statements": 4}},
    "tests/test_servicio.py": {"summary": {"covered_lines": 9, "num_statements": 9}},
}}


def test_parse_junit():
    run = parse_junit(JUNIT)
    assert (run.passed, run.failed, run.skipped) == (1, 2, 1)
    falla, error = run.failures
    assert (falla.name, falla.file, falla.line, falla.kind) == ("test_resta", "tests/test_servicio.py", 7, "failure")
    assert falla.message == "AssertionError: assert 1 == 2"
    assert error.kind == "error" and error.line == 10


def test_parse_junit_invalido():
    assert parse_junit("<no xml").failed == 0
    assert parse_junit(None).passed == 0


def test_parse_audit_sin_duplicados():
    [v] = parse_audit(AUDIT)
    assert (v.package, v.version, v.ids, v.fix_versions) == ("requests", "2.25.1", ["PYSEC-1", "GHSA-2"], ["2.31.0", "2.32.0"])


def test_parse_coverage():
    assert parse_coverage(COVERAGE)["app/core/servicio.py"] == (1, 4)
    assert parse_coverage(None) == {}


def test_ruta_wsl():
    assert _wsl_path(Path("C:/Users/ana/repos/r1")) == "/mnt/c/Users/ana/repos/r1"


@pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16", "utf-8"])
def test_error_del_lanzador_legible(tmp_path, encoding):
    """wsl.exe escribe en UTF-16: el motivo (p. ej. distro no encontrada) debe llegar a la terminal."""
    log = tmp_path / "launcher.log"
    log.write_bytes("There is no distribution with the supplied name.\r\nError code: Wsl/Service/WSL_E_DISTRO_NOT_FOUND\r\n".encode(encoding))
    assert sandbox._read_launcher(log).splitlines()[-1] == "Error code: Wsl/Service/WSL_E_DISTRO_NOT_FOUND"


def test_apagado_no_arranca(settings):
    assert sandbox.start(settings, "r1") == (None, None)


def test_no_disponible_avisa(settings, monkeypatch):
    monkeypatch.setattr(sandbox.shutil, "which", lambda _: None)
    run, reason = sandbox.start(settings.model_copy(update={"sandbox": "wsl"}), "r1")
    assert run is None and "wsl.exe" in reason


class FakeRun:
    """Sandbox que ya terminó, con los resultados de arriba."""

    def __init__(self, codes: dict[str, int | None], tails: dict[str, str] | None = None):
        tails = tails or {}
        self.out = SandboxOutput(
            phases={p: PhaseResult(p, codes.get(p, 0), tails.get(p, "")) for p in PHASES},
            audit=AUDIT, junit=JUNIT if codes.get("tests", 0) in (0, 1) else None, coverage=COVERAGE,
        )
        self.closed = False

    async def wait(self, name: str) -> PhaseResult:
        return self.out.phases[name]

    def output(self) -> SandboxOutput:
        return self.out

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_run(monkeypatch):
    def install(run: FakeRun) -> FakeRun:
        monkeypatch.setattr(sandbox, "start", lambda settings, repo_id: (run, None))
        return run

    return install


def analyze(client) -> tuple[dict, dict]:
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    assert job["status"] == "done", job
    return job, client.get(f"/api/report/{job['report_id']}").json()


def test_job_usa_resultados_reales(client, fake_run):
    run = fake_run(FakeRun({"tests": 1}))
    job, report = analyze(client)
    assert run.closed
    logs = "\n".join(job["logs"])
    assert "entorno listo" in logs and "1 paquete(s) vulnerable(s)" in logs and "1 passed, 2 failed, 1 skipped" in logs
    assert "(simulado)" not in logs

    by_tool = {}
    for f in report["findings"]:
        by_tool.setdefault(f["tool"], []).append(f)
    [vuln] = by_tool["pip-audit"]
    assert vuln["rule"] == "requests 2.25.1" and "PYSEC-1, GHSA-2" in vuln["msg"] and "2.31.0" in vuln["rec"]
    assert {(f["rule"], f["line"]) for f in by_tool["pytest"]} == {("FAIL", 7), ("ERROR", 10)}
    # Cobertura medida: main.py 100 %, servicio.py 25 %, app/__init__.py sin medir (0 %); las pruebas no cuentan
    cov = {c["file"]: c["percent"] for c in report["coverage"]}
    assert cov == {"main.py": 100.0, "app/core/servicio.py": 25.0, "app/__init__.py": 0.0}
    assert report["summary"]["coverage_total"] == 40.0
    assert report["summary"]["tests_failed"] == 2
    assert all("simulado" not in f["msg"] for f in report["findings"])


def test_falla_instalacion_es_hallazgo(client, fake_run):
    fake_run(FakeRun({"install": 1, "tests": 2}, {"install": "No solution found when resolving dependencies"}))
    job, report = analyze(client)
    rules = {f["rule"]: f for f in report["findings"] if f["tool"] == "pytest"}
    assert "No solution found" in rules["DEPS"]["why"]
    assert "ERROR" in rules and "código 2" in rules["ERROR"]["msg"]
    assert "ERROR al instalar: No solution found" in "\n".join(job["logs"])


def test_sandbox_roto_vuelve_a_simular(client, fake_run):
    run = fake_run(FakeRun({"venv": 127, "install": None, "audit": None, "tests": None, "coverage": None}, {"venv": "bash: uv: command not found"}))
    job, report = analyze(client)
    logs = "\n".join(job["logs"])
    assert "no se pudo crear el entorno: bash: uv: command not found" in logs
    assert "(simulado)" in logs
    assert run.closed
    assert not any(f["tool"] == "pip-audit" for f in report["findings"])


def test_formulario_sin_sandbox_simula(client, fake_run):
    run = fake_run(FakeRun({}))
    job = wait_done(client, client.post("/api/analyze", json={"url": URL, "sandbox": False}).json()["job_id"])
    assert job["status"] == "done"
    assert "(simulado)" in "\n".join(job["logs"])
    assert not run.closed  # nunca se arrancó


def test_health_muestra_el_sandbox(client, settings):
    [svc] = [s for s in client.get("/api/health").json()["services"] if s["id"] == "sandbox"]
    assert svc["label"] == "Apagado"
    settings.sandbox = "wsl"
    [svc] = [s for s in client.get("/api/health").json()["services"] if s["id"] == "sandbox"]
    assert svc["status"] == "ok" and "WSL2" in svc["name"]
