"""Repos y reportes sobre el repo de demostración (Ruff, Bandit y Radon reales, sin red)."""

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


# ─── Repositorios ───


def test_reglas_ignoradas_no_aparecen(client, repo_id):
    report = client.get("/api/report/latest", params={"repo": repo_id}).json()
    assert "B101" not in {f["rule"] for f in report["findings"]}


def test_lista_de_repos(client, repo_id):
    repos = client.get("/api/repos").json()
    assert [r["name"] for r in repos] == ["equipo/api-pagos"]
    assert repos[0]["last_report_num"] == 4 and repos[0]["status"] == "listo" and repos[0]["files"] > 0


def test_otro_usuario_no_ve_el_repo(anon, fake, repo_id):
    # Otra cuenta de GitHub en un cliente sin la sesión de "ana"
    fake.user = fake.user.__class__(id=99, login="eve", name=None, email=None, avatar_url=None)
    intruso = anon
    login(intruso)
    assert intruso.get("/api/repos").json() == []
    assert intruso.get(f"/api/report/{repo_id}-4").status_code == 404
    assert intruso.get("/api/report/latest", params={"repo": repo_id}).status_code == 404


def test_requiere_sesion(anon):
    assert anon.get("/api/report/latest", params={"repo": "r1"}).status_code == 401


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
