"""Paso 2: entorno aislado (app.analysis.sandbox), en el sandbox o en el backend."""

from pathlib import Path

import pytest

from app.analysis import sandbox
from app.analysis.sandbox import PhaseResult, _wsl_path
from tests.test_analysis import URL, wait_done

# Capturada al importar, antes de que conftest.fast_venv la sustituya
REAL_LOCAL_VENV = sandbox.local_venv


class FakeRun:
    """Sandbox que ya terminó con el resultado indicado."""

    def __init__(self, phase: PhaseResult):
        self.phase = phase
        self.closed = False

    async def wait(self) -> PhaseResult:
        return self.phase

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_run(monkeypatch):
    def install(run: FakeRun) -> FakeRun:
        monkeypatch.setattr(sandbox, "start", lambda settings, repo_id: (run, None))
        return run

    return install


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


def test_apagado_no_arranca(settings):
    assert sandbox.start(settings, "r1") == (None, None)


def test_no_disponible_avisa_y_usa_el_backend(client, settings, monkeypatch):
    settings.sandbox = "docker"
    monkeypatch.setattr(sandbox.shutil, "which", lambda _exe: None)
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    assert job["status"] == "done"
    logs = "\n".join(job["logs"])
    assert "aviso: sandbox docker no disponible (no se encontró docker)" in logs
    assert "entorno listo en el backend" in logs


def test_sandbox_crea_el_entorno(client, settings, fake_run):
    settings.sandbox = "wsl"
    run = fake_run(FakeRun(PhaseResult("venv", 0, "copiados 5 archivos\nPython 3.12.7")))
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    assert job["status"] == "done" and run.closed
    assert "entorno listo en el sandbox WSL · Python 3.12.7 · copiados 5 archivos" in "\n".join(job["logs"])


def test_sandbox_sin_uv_detiene_el_analisis(client, settings, fake_run):
    settings.sandbox = "wsl"
    run = fake_run(FakeRun(PhaseResult("venv", 127, "bash: uv: command not found")))
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    assert job["status"] == "error" and job["step"] == 1 and run.closed
    assert job["error"]["title"] == "No se pudo crear el entorno aislado"
    assert "bash: uv: command not found" in job["error"]["detail"]
    [repo] = client.get("/api/repos").json()
    assert repo["status"] == "error" and repo["reports"] == 0


def test_reintentar_retoma_desde_el_entorno(client, settings, fake_run, cloner):
    settings.sandbox = "wsl"
    run = fake_run(FakeRun(PhaseResult("venv", 124, "")))
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    assert "tardó más de lo permitido" in job["error"]["detail"]
    run.phase = PhaseResult("venv", 0, "Python 3.12.7")
    client.post(f"/api/jobs/{job['id']}/retry")
    again = wait_done(client, job["id"])
    assert again["status"] == "done"
    # No volvió a clonar: el reintento empieza en el paso que falló
    assert len(cloner.calls) == 1


def test_formulario_sin_sandbox_no_lo_arranca(client, settings, fake_run, fast_venv):
    settings.sandbox = "wsl"
    run = fake_run(FakeRun(PhaseResult("venv", 0)))
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
