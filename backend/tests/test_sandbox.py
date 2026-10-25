"""Pasos 2, 3 y 5 (app.analysis.sandbox): entorno, dependencias y pip-audit, en el sandbox o en el backend."""

from pathlib import Path

import pytest

from app.analysis import sandbox
from app.analysis.sandbox import PHASES, PhaseResult, SandboxOutput, _wsl_path, parse_audit
from tests.test_analysis import URL, wait_done

# Capturada al importar, antes de que conftest.fast_venv la sustituya
REAL_LOCAL_VENV = sandbox.local_venv

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


class FakeRun:
    """Sandbox que ya terminó: cada fase con su código de salida (0 si no se indica) y su log."""

    def __init__(self, codes: dict[str, int | None] | None = None, logs: dict[str, str] | None = None, audit: dict | None = None):
        self.codes = codes or {}
        self.logs = logs or {}
        self.audit = audit
        self.closed = False

    def _phase(self, name: str) -> PhaseResult:
        return PhaseResult(name, self.codes.get(name, 0), self.logs.get(name, ""))

    async def wait(self, name: str) -> PhaseResult:
        return self._phase(name)

    def output(self) -> SandboxOutput:
        return SandboxOutput(phases={name: self._phase(name) for name in PHASES}, audit=self.audit)

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_run(monkeypatch):
    def install(run: FakeRun) -> FakeRun:
        monkeypatch.setattr(sandbox, "start", lambda settings, repo_id: (run, None))
        return run

    return install


def analyze(client) -> dict:
    return wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])


def counts(client, job: dict) -> dict:
    return client.get(f"/api/repos/{job['repo_id']}/history").json()[0]["findings"]


def test_entorno_local_real(settings):
    """Sin sandbox el backend crea un venv de verdad, fuera del clon."""
    result = REAL_LOCAL_VENV(settings, "r1")
    assert result.ok, result.log_tail
    assert "entorno listo en el backend · Python 3." in sandbox.summary(result, "el backend")
    venv = sandbox.venv_dir(settings, "r1")
    assert (venv / "pyvenv.cfg").is_file()
    assert (venv / "Scripts" / "python.exe").is_file() or (venv / "bin" / "python").is_file()


def test_ruta_wsl():
    assert _wsl_path(Path("C:/Users/ana/repo")) == "/mnt/c/Users/ana/repo"


def test_parse_audit_sin_duplicados():
    [v] = parse_audit(AUDIT)
    assert (v.package, v.version, v.ids, v.fix_versions) == ("requests", "2.25.1", ["PYSEC-1", "GHSA-2"], ["2.31.0", "2.32.0"])


def test_apagado_no_arranca(settings):
    assert sandbox.start(settings, "r1") == (None, None)


def test_no_disponible_avisa_y_usa_el_backend(client, settings, monkeypatch):
    settings.sandbox = "docker"
    monkeypatch.setattr(sandbox.shutil, "which", lambda _exe: None)
    job = analyze(client)
    assert job["status"] == "done"
    logs = "\n".join(job["logs"])
    assert "aviso: sandbox docker no disponible (no se encontró docker); el entorno se crea en el backend y pip-audit no corre" in logs
    assert "entorno listo en el backend" in logs
    assert "omitido: sin sandbox no hay dependencias instaladas que revisar" in logs


def test_sandbox_instala_y_corre_pip_audit(client, settings, fake_run):
    settings.sandbox = "wsl"
    run = fake_run(FakeRun(logs={"venv": "copiados 5 archivos\nPython 3.12.7", "install": "Installed 12 packages in 40ms"}, audit=AUDIT))
    job = analyze(client)
    assert job["status"] == "done" and run.closed
    logs = "\n".join(job["logs"])
    assert "entorno listo en el sandbox WSL · Python 3.12.7 · copiados 5 archivos" in logs
    assert "Installed 12 packages in 40ms" in logs and "1 paquete(s) vulnerable(s)" in logs
    assert job["logs"][-1] == "Análisis #1 guardado en el repositorio con 1 hallazgo(s) de seguridad."
    assert counts(client, job) == {"alta": 1, "media": 0, "baja": 0}


def test_falla_instalacion_es_hallazgo_y_no_detiene(client, settings, fake_run):
    settings.sandbox = "wsl"
    fake_run(FakeRun({"install": 1}, {"install": "No solution found when resolving dependencies"}, audit={"dependencies": []}))
    job = analyze(client)
    assert job["status"] == "done"
    assert "ERROR al instalar: No solution found when resolving dependencies" in "\n".join(job["logs"])
    assert counts(client, job) == {"alta": 1, "media": 0, "baja": 0}


def test_pip_audit_sin_resultado_avisa(client, settings, fake_run):
    settings.sandbox = "wsl"
    fake_run(FakeRun({"audit": 1}, {"audit": "ERROR: network unreachable"}))
    job = analyze(client)
    assert job["status"] == "done"
    assert "pip-audit no devolvió resultado: ERROR: network unreachable" in "\n".join(job["logs"])


def test_sandbox_sin_uv_detiene_el_analisis(client, settings, fake_run):
    settings.sandbox = "wsl"
    run = fake_run(FakeRun({"venv": 127}, {"venv": "bash: uv: command not found"}))
    job = analyze(client)
    assert job["status"] == "error" and job["step"] == 1 and run.closed
    assert job["error"]["title"] == "No se pudo crear el entorno aislado"
    assert "bash: uv: command not found" in job["error"]["detail"]
    [repo] = client.get("/api/repos").json()
    assert repo["status"] == "error" and repo["reports"] == 0


def test_reintentar_retoma_desde_el_entorno(client, settings, fake_run, cloner):
    settings.sandbox = "wsl"
    run = fake_run(FakeRun({"venv": 124}))
    job = analyze(client)
    assert "tardó más de lo permitido" in job["error"]["detail"]
    run.codes = {}
    client.post(f"/api/jobs/{job['id']}/retry")
    again = wait_done(client, job["id"])
    assert again["status"] == "done" and again["step"] == 5
    # No volvió a clonar: el reintento empieza en el paso que falló
    assert len(cloner.calls) == 1


def test_formulario_sin_sandbox_no_lo_arranca(client, settings, fake_run, fast_venv):
    settings.sandbox = "wsl"
    run = fake_run(FakeRun())
    job = wait_done(client, client.post("/api/analyze", json={"url": URL, "sandbox": False}).json()["job_id"])
    assert job["status"] == "done" and not run.closed
    assert fast_venv == [job["repo_id"]]


def test_health_muestra_el_sandbox_y_github(client, settings):
    services = {s["id"]: s for s in client.get("/api/health").json()["services"]}
    assert set(services) == {"github", "sandbox", "tunnel"}
    assert services["sandbox"]["label"] == "Apagado" and services["github"]["status"] == "ok"
    settings.sandbox = "wsl"
    [svc] = [s for s in client.get("/api/health").json()["services"] if s["id"] == "sandbox"]
    assert svc["status"] == "ok" and "WSL2" in svc["name"]
