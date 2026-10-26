"""
Jobs persistentes (tabla jobs) y analizadores elegidos. "Otro worker" = otra app con su propio JobManager
sobre la misma base de datos, como dos procesos de uvicorn.
"""

import time

import pytest
from fastapi.testclient import TestClient

from app.analysis import jobs as jobs_mod
from app.analysis import router as analysis_router
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
    assert any("[01/10] Clonando repositorio" in line for line in again["logs"][again["logs"].index("— Reintentando —"):])


def test_un_job_vivo_en_otro_worker_bloquea_otro_analisis(client, worker2, settings):
    settings.job_step_seconds = 0.3
    job_id = start(client)
    res = worker2.post("/api/analyze", json={"url": URL})
    assert res.status_code == 409 and res.json()["error"]["code"] == "already_running"
    [repo] = worker2.get("/api/repos").json()
    assert repo["status"] == "analizando" and repo["progress"]["job_id"] == job_id
    settings.job_step_seconds = 0
    wait_done(client, job_id, timeout=15)


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
    assert steps_done == sorted(set(steps_done)) and steps_done[-1] == 9


# ─── Analizadores elegidos ───


def test_cada_categoria_necesita_un_analizador(client):
    res = client.post("/api/analyze", json={"url": URL, "analyzers": ["bandit", "ruff"]})
    assert res.status_code == 422 and res.json()["error"]["message"] == "Elige al menos un analizador de: Pruebas"


def test_solo_corren_los_elegidos(client):
    job = wait_done(client, start(client, analyzers=["bandit", "coverage", "radon"]))
    logs = "\n".join(job["logs"])
    for name in ("pip-audit", "pytest", "Ruff"):
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
