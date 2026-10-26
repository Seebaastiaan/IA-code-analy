import time

import pytest
from starlette.websockets import WebSocketDisconnect

from app.analysis import fake
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


def test_analisis_guarda_reporte_y_aparece_en_repos(client):
    job_id = client.post("/api/analyze", json={"url": URL, "branch": "develop", "analyzers": ["bandit", "pytest", "ruff"]}).json()["job_id"]
    job = wait_done(client, job_id)
    assert job["status"] == "done"
    assert job["step"] == job["total"] == len(fake.JOB_STEPS)
    assert job["logs"][-1] == "Análisis #1 completado."

    [repo] = client.get("/api/repos").json()
    assert repo["name"] == "ana/api-pagos"
    assert repo["status"] == "listo"
    assert repo["branch"] == "develop"
    assert repo["last_report_id"] == job["report_id"]
    assert set(repo["scores"]) == {"seg", "test", "prac", "global"}

    report = client.get(f"/api/report/{job['report_id']}").json()
    assert report["num"] == 1 and report["prev"] is None
    assert report["scores"] == repo["scores"]
    # El mismo reporte se ve igual en cada consulta (métricas derivadas de la semilla)
    assert client.get("/api/report/latest", params={"repo": repo["id"]}).json() == report


def test_clonado_real_cuenta_py_y_guarda_commit(client, cloner):
    job = wait_done(client, client.post("/api/analyze", json={"url": URL + ".git"}).json()["job_id"])
    # El paso 1 recibe la URL normalizada y el token de GitHub del usuario (para repos privados)
    assert cloner.calls == [{"url": URL, "branch": "main", "token": GH_TOKEN}]
    assert any("commit abc1234 · 3 archivos .py" in line for line in job["logs"])
    [repo] = client.get("/api/repos").json()
    assert repo["files"] == 3
    assert client.get(f"/api/report/{job['report_id']}").json()["commit"] == "abc1234"


def test_arbol_y_archivos_del_clon(client):
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    repo_id = job["repo_id"]
    tree = client.get(f"/api/repos/{repo_id}/tree").json()
    # Archivos de texto, sin .git, ordenados por carpeta
    assert [e["path"] for e in tree] == ["README.md", "main.py", "app/__init__.py", "app/core/servicio.py"]
    assert tree[3]["dir"] == "app/core"

    file = client.get("/api/file", params={"repo": repo_id, "path": "app/core/servicio.py"}).json()
    # El editor conserva los saltos de línea del archivo (en Windows el clon falso los escribe como \r\n)
    assert file["path"] == "app/core/servicio.py" and file["language"] == "python"
    assert file["content"].replace("\r\n", "\n") == "def suma(a, b):\n    return a + b\n"
    assert client.get("/api/file", params={"repo": repo_id, "path": "README.md"}).json()["language"] == "markdown"
    # Fuera del clon u oculto: 400; inexistente: 404
    for bad, status in (("../../secrets.json", 400), (".git/oculto.py", 400), ("no/existe.py", 404)):
        assert client.get("/api/file", params={"repo": repo_id, "path": bad}).status_code == status, bad


def test_arbol_sin_clon(client):
    # El clonado falla, así que el repo existe pero nunca tuvo clon
    job_id = client.post("/api/analyze", json={"url": "https://github.com/ana/nuevo", "branch": "no-existe"}).json()["job_id"]
    job = wait_done(client, job_id)
    res = client.get(f"/api/repos/{job['repo_id']}/tree")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_cloned"


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


def test_fallo_al_clonar_detiene_el_analisis(client):
    job = wait_done(client, client.post("/api/analyze", json={"url": URL, "branch": "no-existe"}).json()["job_id"])
    assert job["status"] == "error"
    assert job["step"] == 0
    assert job["error"]["title"] == "La rama no existe"
    assert job["report_id"] is None
    [repo] = client.get("/api/repos").json()
    assert repo["status"] == "error" and repo["error"] == "La rama no existe"


def test_reanalizar_crea_reporte_2_con_anterior(client):
    first = wait_done(client, client.post("/api/analyze", json={"url": URL + ".git"}).json()["job_id"])
    repo_id = first["repo_id"]
    second = wait_done(client, client.post(f"/api/repos/{repo_id}/analyze").json()["job_id"])
    assert second["repo_id"] == repo_id
    report = client.get(f"/api/report/{second['report_id']}").json()
    assert report["num"] == 2
    assert report["prev"]["num"] == 1
    assert len(client.get("/api/repos").json()) == 1


def test_websocket_envia_snapshot_y_avance(client, settings):
    # Pasos lentos para conectarse antes de que termine (si no, solo llega el snapshot final)
    settings.job_step_seconds = 0.05
    job_id = client.post("/api/analyze", json={"url": URL}).json()["job_id"]
    with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
        first = ws.receive_json()
        assert first["type"] == "snapshot" and first["job"]["id"] == job_id
        assert first["job"]["status"] == "running"
        types = []
        while not types or types[-1] != "done":
            types.append(ws.receive_json()["type"])
    assert "step" in types and "step_done" in types and "log" in types


def test_websocket_job_inexistente(client):
    with client.websocket_connect("/ws/jobs/job-nope") as ws, pytest.raises(WebSocketDisconnect):
        ws.receive_json()


def test_cancelar(client, settings):
    settings.job_step_seconds = 0.2
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


def test_tablero(client):
    assert client.get("/api/dashboard").json()["selected"] is None
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    dash = client.get("/api/dashboard").json()
    assert dash["active_repos"] == 1
    assert dash["selected"]["report_id"] == job["report_id"]
    assert len(dash["selected"]["history"]) == 1


def test_cada_usuario_ve_solo_sus_repos(client, anon, fake):
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    # Otra cuenta de GitHub en el mismo cliente
    fake.user = fake.user.__class__(id=99, login="beto", name=None, email=None, avatar_url=None)
    login(anon)
    assert anon.get("/api/repos").json() == []
    assert anon.get(f"/api/report/{job['report_id']}").status_code == 404
    assert anon.get(f"/api/jobs/{job['id']}").status_code == 404


def test_metricas_falsas_coherentes():
    cat = {"seg": 40, "test": 90, "prac": 70}
    d = fake.details(123, cat)
    assert d == fake.details(123, cat)
    assert all(0 <= c["percent"] <= 100 for c in d["coverage"])
    assert d["summary"]["tests_failed"] == sum(f["rule"] == "FAIL" for f in d["findings"])
    assert fake.global_score(cat) == 61.0  # (50·40 + 30·90 + 20·70) / 100
