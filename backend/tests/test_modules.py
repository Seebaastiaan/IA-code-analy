"""Tablero, reporte y archivos del clon sobre el repo de demostración (Ruff, Bandit y Radon reales, sin red)."""


import pytest

from app.seed import seed
from tests.conftest import login


@pytest.fixture
def repo_id(client, settings) -> str:
    """Repo de demostración del usuario "ana" (el que inicia sesión en conftest)."""
    return seed("ana", settings)


def finding(client, repo_id, **match) -> dict:
    report = client.get("/api/report/latest", params={"repo": repo_id}).json()
    return next(f for f in report["findings"] if all(f[k] == v for k, v in match.items()))


# ─── Tablero ───


def test_tablero_sin_repos(client):
    body = client.get("/api/dashboard").json()
    assert body == {"active_repos": 0, "repos": [], "thresholds": {"score": 70, "cov": 60}, "selected": None}


def test_tablero(client, repo_id):
    body = client.get("/api/dashboard").json()
    sel = body["selected"]
    assert body["active_repos"] == 1
    assert sel["repo"]["id"] == repo_id and sel["num"] == 4
    assert [h["date"] for h in sel["history"]] == sorted(h["date"] for h in sel["history"])
    assert len(sel["history"]) == 4
    # Los análisis anteriores tenían más hallazgos: el score mejora
    assert sel["scores"]["global"] > sel["prev_scores"]["global"]
    assert sel["history"][-1]["global"] == sel["scores"]["global"]
    sevs = [f["sev"] for f in sel["top_findings"]]
    assert len(sevs) == 4 and sevs == sorted(sevs, key=["alta", "media", "baja"].index)
    assert sel["open_findings"] >= 4
    assert set(sel["scores"]) == {"global", "seg", "test", "prac"}


def test_reglas_ignoradas_no_aparecen(client, repo_id):
    report = client.get("/api/report/latest", params={"repo": repo_id}).json()
    assert "B101" not in {f["rule"] for f in report["findings"]}


def test_lista_de_repos_e_historial(client, repo_id):
    repos = client.get("/api/repos").json()
    assert [r["name"] for r in repos] == ["equipo/api-pagos"]
    assert repos[0]["last_report_num"] == 4 and repos[0]["status"] == "listo" and repos[0]["files"] > 0
    assert len(client.get(f"/api/repos/{repo_id}/history", params={"limit": 2}).json()) == 2


def test_otro_usuario_no_ve_el_repo(anon, fake, repo_id):
    # Otra cuenta de GitHub en un cliente sin la sesión de "ana"
    fake.user = fake.user.__class__(id=99, login="eve", name=None, email=None, avatar_url=None)
    intruso = anon
    login(intruso)
    assert intruso.get("/api/dashboard").json()["selected"] is None
    assert intruso.get(f"/api/report/{repo_id}-4").status_code == 404
    assert intruso.get(f"/api/repos/{repo_id}/tree").status_code == 404
    assert intruso.get("/api/file", params={"repo": repo_id, "path": "api.py"}).status_code == 404
    assert intruso.post("/api/fix", json={"repo_id": repo_id, "finding_ids": [1]}).status_code == 404


def test_requiere_sesion(anon):
    assert anon.get("/api/dashboard").status_code == 401


# ─── Reportes ───


def test_reporte(client, repo_id):
    latest = client.get("/api/report/latest", params={"repo": repo_id}).json()
    assert latest == client.get(f"/api/report/{repo_id}-4").json()
    assert latest["prev"]["num"] == 3
    assert latest["weights"] == {"seg": 50, "test": 30, "prac": 20}
    assert latest["complexity"][0]["fn"] == "procesar" and latest["complexity"][0]["grade"] in "BCDEF"
    f = finding(client, repo_id, rule="B602")
    assert f["sev"] == "alta" and f["cat"] == "seg" and f["file"] == "api.py"
    assert any("shell=True" in line["text"] for line in f["snippet"])
    w = latest["weights"]
    s = latest["scores"]
    assert s["global"] == round((w["seg"] * s["seg"] + w["test"] * s["test"] + w["prac"] * s["prac"]) / 100, 1)


def test_reporte_inexistente(client, repo_id):
    assert client.get(f"/api/report/{repo_id}-99").status_code == 404
    assert client.get("/api/report/latest").status_code == 422


# ─── Archivos del clon ───


def test_leer_archivo(client, repo_id):
    res = client.get("/api/file", params={"repo": repo_id, "path": "pagos/procesador.py"}).json()
    assert res["language"] == "python" and res["content"].startswith("from decimal import Decimal")


@pytest.mark.parametrize("path", ["../t.db", "..\\t.db", "/etc/passwd", ".git/config", "pagos/../../t.db", "", "C:/Windows/win.ini"])
def test_rutas_no_validas(client, repo_id, path):
    res = client.get("/api/file", params={"repo": repo_id, "path": path})
    assert res.status_code in (400, 404, 422)
    assert res.json()["error"]["code"] in ("invalid_path", "not_found", "invalid_request")


def test_archivo_inexistente(client, repo_id):
    assert client.get("/api/file", params={"repo": repo_id, "path": "nada.py"}).status_code == 404
