"""Análisis del Sprint 4: clonar → crear entorno aislado → guardar el análisis en el repositorio."""

import time

import pytest
from starlette.websockets import WebSocketDisconnect

from app.analysis.steps import JOB_STEPS
from tests.conftest import GH_TOKEN, login

URL = "https://github.com/ana/api-pagos"


def wait_done(client, job_id: str, timeout: float = 5) -> dict:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "running":
            return job
        time.sleep(0.02)
    pytest.fail("el job no terminó")


def test_analisis_llega_al_entorno_y_se_guarda_en_repos(client):
    job_id = client.post("/api/analyze", json={"url": URL, "branch": "develop"}).json()["job_id"]
    job = wait_done(client, job_id)
    assert job["status"] == "done"
    assert job["step"] == job["total"] == len(JOB_STEPS) == 2
    assert job["logs"][-1] == "Análisis #1 guardado en el repositorio."
    logs = "\n".join(job["logs"])
    assert "[01/2] Clonando repositorio" in logs and "[02/2] Creando entorno aislado" in logs
    assert "entorno listo en el backend · Python 3.12.7" in logs

    [repo] = client.get("/api/repos").json()
    assert repo["name"] == "ana/api-pagos"
    assert repo["status"] == "listo" and repo["branch"] == "develop"
    assert repo["last_report_id"] == job["report_id"] and repo["last_report_num"] == 1 and repo["reports"] == 1
    assert "scores" not in repo


def test_clonado_real_cuenta_py_y_guarda_commit(client, cloner):
    job = wait_done(client, client.post("/api/analyze", json={"url": URL + ".git"}).json()["job_id"])
    # El paso 1 recibe la URL normalizada y el token de GitHub del usuario (para repos privados)
    assert cloner.calls == [{"url": URL, "branch": "main", "token": GH_TOKEN}]
    assert any("commit abc1234 · 3 archivos .py" in line for line in job["logs"])
    [repo] = client.get("/api/repos").json()
    assert repo["files"] == 3 and repo["commit"] == "abc1234"


def test_historial_de_analisis_guardados(client):
    first = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    repo_id = first["repo_id"]
    second = wait_done(client, client.post(f"/api/repos/{repo_id}/analyze").json()["job_id"])
    assert second["repo_id"] == repo_id and second["logs"][-1] == "Análisis #2 guardado en el repositorio."
    history = client.get(f"/api/repos/{repo_id}/history").json()
    assert [h["num"] for h in history] == [2, 1]
    assert history[0]["id"] == second["report_id"] and history[0]["commit"] == "abc1234" and history[0]["branch"] == "main"
    assert {"name": "Python", "files": 3} in history[0]["languages"]
    assert len(client.get("/api/repos").json()) == 1


def test_arbol_y_archivos_del_clon(client):
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    repo_id = job["repo_id"]
    tree = client.get(f"/api/repos/{repo_id}/tree").json()
    # Archivos de texto, sin .git, ordenados por carpeta
    assert [e["path"] for e in tree] == ["README.md", "main.py", "app/__init__.py", "app/core/servicio.py"]
    assert tree[3]["dir"] == "app/core"

    file = client.get("/api/file", params={"repo": repo_id, "path": "app/core/servicio.py"}).json()
    assert file["path"] == "app/core/servicio.py" and file["language"] == "python"
    assert file["content"].replace("\r\n", "\n") == "def suma(a, b):\n    return a + b\n"
    # Fuera del clon u oculto: 400; inexistente: 404
    for bad, status in (("../../secrets.json", 400), (".git/oculto.py", 400), ("no/existe.py", 404)):
        assert client.get("/api/file", params={"repo": repo_id, "path": bad}).status_code == status, bad
    # Solo lectura: el editor llega en otro sprint
    assert client.put("/api/file", json={"repo_id": repo_id, "path": "main.py", "content": ""}).status_code == 405


def test_arbol_sin_clon(client):
    job = wait_done(client, client.post("/api/analyze", json={"url": "https://github.com/ana/nuevo", "branch": "no-existe"}).json()["job_id"])
    res = client.get(f"/api/repos/{job['repo_id']}/tree")
    assert res.status_code == 404 and res.json()["error"]["code"] == "not_cloned"


def test_fallo_al_clonar_detiene_el_analisis(client, fast_venv):
    job = wait_done(client, client.post("/api/analyze", json={"url": URL, "branch": "no-existe"}).json()["job_id"])
    assert job["status"] == "error" and job["step"] == 0
    assert job["error"]["title"] == "La rama no existe"
    assert job["report_id"] is None
    assert fast_venv == []  # nunca llegó a crear el entorno
    [repo] = client.get("/api/repos").json()
    assert repo["status"] == "error" and repo["error"] == "La rama no existe" and repo["reports"] == 0


def test_error_inesperado_no_deja_el_job_colgado(client, cloner, monkeypatch):
    # Caso real: OneDrive bloquea la carpeta recién clonada y el renombrado da "Access denied"
    def locked(*_):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(cloner, "promote", locked)
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    assert job["status"] == "error"
    assert job["error"]["title"] == "Error inesperado durante el análisis"
    assert "PermissionError" in job["error"]["detail"]


def test_promote_reintenta_y_copia_si_no_puede_renombrar(settings, monkeypatch):
    from pathlib import Path

    from app.analysis import clone

    tmp = clone.clones_root(settings) / "r1.tmp-a"
    (tmp / "pkg").mkdir(parents=True)
    (tmp / "pkg" / "m.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(clone.time, "sleep", lambda _s: None)
    monkeypatch.setattr(Path, "rename", lambda *_: (_ for _ in ()).throw(PermissionError(5, "Access is denied")))
    clone.promote(settings, "r1", "a")
    assert clone.python_files(clone.clone_dir(settings, "r1")) == ["pkg/m.py"]


def test_websocket_envia_snapshot_y_avance(client, settings):
    # Pausa para conectarse antes de que termine (si no, solo llega el snapshot final)
    settings.job_step_seconds = 0.1
    job_id = client.post("/api/analyze", json={"url": URL}).json()["job_id"]
    with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
        first = ws.receive_json()
        assert first["type"] == "snapshot" and first["job"]["id"] == job_id
        msgs = []
        while not msgs or msgs[-1]["type"] != "done":
            msgs.append(ws.receive_json())
    types = [m["type"] for m in msgs]
    assert "step" in types and "step_done" in types and "log" in types
    assert msgs[-1] == {"type": "done", "repo_id": msgs[-1]["repo_id"], "report_id": msgs[-1]["report_id"], "num": 1}


def test_websocket_job_inexistente(client):
    with client.websocket_connect("/ws/jobs/job-nope") as ws, pytest.raises(WebSocketDisconnect):
        ws.receive_json()


def test_cancelar_y_reintentar(client, settings):
    settings.job_step_seconds = 0.3
    job_id = client.post("/api/analyze", json={"url": URL}).json()["job_id"]
    assert client.delete(f"/api/jobs/{job_id}").status_code == 204
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "cancelled"
    [repo] = client.get("/api/repos").json()
    assert repo["status"] == "error" and repo["error"] == "Análisis cancelado"
    # Reintentar retoma el mismo job
    settings.job_step_seconds = 0
    assert client.post(f"/api/jobs/{job_id}/retry").json()["job_id"] == job_id
    assert wait_done(client, job_id)["status"] == "done"


@pytest.mark.parametrize("url", ["no-es-url", "http://github.com/ana/repo", "https://gitlab.com/ana/repo", "https://github.com/ana", "https://10.0.0.1/ana/repo"])
def test_url_invalida(client, url):
    res = client.post("/api/analyze", json={"url": url})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "invalid_url"


@pytest.mark.parametrize("branch", ["--upload-pack=touch x", "a..b", "rama con espacio"])
def test_rama_invalida(client, branch):
    res = client.post("/api/analyze", json={"url": URL, "branch": branch})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "invalid_branch"


def test_cada_usuario_ve_solo_sus_repos(client, anon, fake):
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    # Otra cuenta de GitHub en el mismo cliente
    fake.user = fake.user.__class__(id=99, login="beto", name=None, email=None, avatar_url=None)
    login(anon)
    assert anon.get("/api/repos").json() == []
    assert anon.get(f"/api/repos/{job['repo_id']}/history").status_code == 404
    assert anon.get(f"/api/jobs/{job['id']}").status_code == 404


@pytest.mark.parametrize("path", ["/api/dashboard", "/api/report/latest", "/api/chat", "/api/diff", "/api/fix"])
def test_fuera_del_sprint_4(client, path):
    """Tablero, reporte, asistente IA, comparativa y correcciones llegan en los siguientes sprints."""
    assert client.request("POST" if path in ("/api/chat", "/api/diff", "/api/fix") else "GET", path).status_code in (404, 405)
