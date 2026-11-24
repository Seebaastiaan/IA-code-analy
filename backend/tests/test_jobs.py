"""
Jobs persistentes (tabla jobs) y analizadores elegidos. "Otro worker" = otra app con su propio JobManager
sobre la misma base de datos, como dos procesos de uvicorn.
"""

import time
from threading import Event

import pytest
from fastapi.testclient import TestClient

from app.analyses.workspace import Workspace
from app.analysis import fake
from app.analysis import jobs as jobs_mod
from app.analysis import router as analysis_router
from app.analysis.clone import clone_dir
from app.analysis.jobs import JobManager
from app.db import connect
from app.main import create_app
from tests.test_analysis import URL, wait_done


@pytest.fixture
def worker2(client, settings, cloner):
    """Segundo worker: misma base y sesión, otro JobManager."""
    app = create_app()
    app.dependency_overrides.update(client.app.dependency_overrides)
    other = JobManager(cloner)
    app.dependency_overrides[analysis_router.get_jobs] = lambda: other
    with TestClient(app) as c:
        c.headers["Authorization"] = client.headers["Authorization"]
        yield c


def start(client, **body) -> str:
    res = client.post("/api/analyze", json={"url": URL, **body})
    assert res.status_code == 200, res.text
    return res.json()["job_id"]


# ─── Persistencia ───


def test_otro_worker_ve_el_job_terminado(client, worker2):
    job = wait_done(client, start(client))
    remote = worker2.get(f"/api/jobs/{job['id']}").json()
    assert remote["status"] == "done" and remote["logs"] == job["logs"] and remote["report_id"] == job["report_id"]


def test_job_interrumpido_se_ve_como_error_y_se_reintenta(client, worker2, settings):
    job = wait_done(client, start(client))
    conn = connect(settings.database_path)
    # Simula un análisis que quedó a medias porque el servidor se reinició
    conn.execute("UPDATE jobs SET status = 'running', step = 4, heartbeat = ? WHERE id = ?", (time.time() - 120, job["id"]))
    conn.execute("UPDATE repos SET status = 'analizando'")
    conn.commit()

    snap = worker2.get(f"/api/jobs/{job['id']}").json()
    assert snap["status"] == "error" and snap["error"]["title"] == "El análisis se interrumpió"
    [repo] = worker2.get("/api/repos").json()
    assert repo["status"] == "listo"  # tiene un reporte anterior

    assert worker2.post(f"/api/jobs/{job['id']}/retry").status_code == 200
    again = wait_done(worker2, job["id"])
    assert again["status"] == "done" and "— Reintentando —" in again["logs"]
    assert any(f"[01/{len(fake.JOB_STEPS)}] Clonando repositorio" in line for line in again["logs"][again["logs"].index("— Reintentando —"):])


def test_un_job_vivo_en_otro_worker_bloquea_otro_analisis(client, worker2, settings):
    settings.job_step_seconds = 0.3
    job_id = start(client)
    res = worker2.post("/api/analyze", json={"url": URL})
    assert res.status_code == 409 and res.json()["error"]["code"] == "already_running"
    [repo] = worker2.get("/api/repos").json()
    assert repo["status"] == "analizando" and repo["progress"]["job_id"] == job_id
    settings.job_step_seconds = 0
    wait_done(client, job_id, timeout=15)


def test_quitar_repo_desde_otro_worker_borra_historial_y_permite_agregar_de_nuevo(client, worker2, settings):
    settings.job_step_seconds = 0.2
    job_id = start(client)
    repo_id = client.get(f"/api/jobs/{job_id}").json()["repo_id"]
    path = f"/api/repos/{repo_id}"
    blocked = worker2.delete(path)
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "already_running"
    settings.job_step_seconds = 0
    job = wait_done(client, job_id)
    shared = client.post(f"/api/report/{job['report_id']}/share", json={})
    assert shared.status_code == 200, shared.text
    backup = Workspace(settings, repo_id).backup_root
    backup.mkdir(parents=True)
    assert clone_dir(settings, repo_id).is_dir()

    assert worker2.delete(path).status_code == 204
    assert client.get("/api/repos").json() == []
    assert client.get("/api/dashboard").json()["selected"] is None
    assert client.get(f"/api/report/{job['report_id']}").status_code == 404
    assert client.get(f"/api/public/r/{shared.json()['share_id']}").status_code == 404
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
    assert client.post(f"/api/jobs/{job_id}/retry").status_code == 404
    assert client.post(f"{path}/analyze").status_code == 404
    assert worker2.delete(path).status_code == 404
    assert not clone_dir(settings, repo_id).exists() and not backup.exists()

    readded = wait_done(client, start(client))
    assert readded["repo_id"] != repo_id
    assert client.get(f"/api/report/{readded['report_id']}").json()["num"] == 1


def test_quitar_repo_cancelado_limpia_un_clon_que_termina_tarde(client, settings, cloner, monkeypatch):
    started = Event()
    resume = Event()
    promoted = Event()

    def slow_promote(settings, repo_id, attempt):
        started.set()
        if resume.wait(5):
            # Simula al hilo de promoción cuando publica una carpeta después de la cancelación.
            clone_dir(settings, repo_id).mkdir()
            promoted.set()

    monkeypatch.setattr(cloner, "promote", slow_promote)
    job_id = start(client)
    repo_id = client.get(f"/api/jobs/{job_id}").json()["repo_id"]
    try:
        assert started.wait(5)
        assert client.delete(f"/api/jobs/{job_id}").status_code == 204
        assert client.delete(f"/api/repos/{repo_id}").status_code == 204
    finally:
        resume.set()
    assert promoted.wait(5)
    end = time.monotonic() + 5
    while clone_dir(settings, repo_id).exists() and time.monotonic() < end:
        time.sleep(0.02)
    assert not clone_dir(settings, repo_id).exists()


def test_cancelar_desde_otro_worker(client, worker2, settings, monkeypatch):
    monkeypatch.setattr(jobs_mod, "HEARTBEAT_S", 0.05)
    settings.job_step_seconds = 0.3
    job_id = start(client)
    assert worker2.delete(f"/api/jobs/{job_id}").status_code == 204
    end = time.monotonic() + 5
    while client.get(f"/api/jobs/{job_id}").json()["status"] == "running" and time.monotonic() < end:
        time.sleep(0.05)
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "cancelled"


def test_websocket_de_un_job_en_otro_worker(client, worker2, settings, monkeypatch):
    monkeypatch.setattr(jobs_mod, "REMOTE_POLL_S", 0.02)
    settings.job_step_seconds = 0.05
    job_id = start(client)
    types, steps_done = [], []
    with worker2.websocket_connect(f"/ws/jobs/{job_id}") as ws:
        while True:
            msg = ws.receive_json()
            types.append(msg["type"])
            if msg["type"] == "step_done":
                steps_done.append(msg["index"])
            if msg["type"] in ("done", "error"):
                break
    assert types[0] == "snapshot" and types[-1] == "done"
    assert "log" in types and "step" in types
    assert steps_done == sorted(set(steps_done)) and steps_done[-1] == len(fake.JOB_STEPS) - 1


# ─── Analizadores elegidos ───


def test_cada_categoria_necesita_un_analizador(client):
    res = client.post("/api/analyze", json={"url": URL, "analyzers": ["bandit", "ruff"]})
    assert res.status_code == 422 and res.json()["error"]["message"] == "Elige al menos un analizador de: Pruebas"


def test_solo_corren_los_elegidos(client):
    job = wait_done(client, start(client, analyzers=["bandit", "coverage", "radon"], index=False))
    logs = "\n".join(job["logs"])
    for name in ("pip-audit", "pytest", "Ruff", "Indexando para el asistente"):
        block = logs.split(f"] {name} →", 1)[1].split("\n[", 1)[0]
        assert "omitido (no seleccionado)" in block, name
    report = client.get(f"/api/report/{job['report_id']}").json()
    assert report["analyzers"] == ["bandit", "coverage", "radon"]
    assert {f["tool"] for f in report["findings"]} <= {"Bandit", "coverage"}
    assert report["summary"]["tests_failed"] == 0 and report["summary"]["coverage_total"] is not None


def test_sin_coverage_la_cobertura_no_se_mide(client):
    job = wait_done(client, start(client, analyzers=["bandit", "pytest", "ruff"]))
    report = client.get(f"/api/report/{job['report_id']}").json()
    assert report["summary"]["coverage_total"] is None and report["coverage"] == []
    assert not any(f["tool"] == "coverage" for f in report["findings"])
    # Sin cobertura, el score de pruebas solo descuenta las que fallan
    assert report["scores"]["test"] == 100 - 5 * report["summary"]["tests_failed"]


def test_reanalizar_repite_los_analizadores(client):
    job = wait_done(client, start(client, analyzers=["bandit", "pytest", "radon"]))
    again = wait_done(client, client.post(f"/api/repos/{job['repo_id']}/analyze").json()["job_id"])
    assert client.get(f"/api/report/{again['report_id']}").json()["analyzers"] == ["bandit", "pytest", "radon"]


def test_sin_analizadores_corren_todos(client):
    job = wait_done(client, start(client))
    assert client.get(f"/api/report/{job['report_id']}").json()["analyzers"] == ["bandit", "pip-audit", "pytest", "coverage", "ruff", "radon"]
