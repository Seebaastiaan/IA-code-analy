"""Repositorios y análisis guardados sobre el repo de demostración (golden repo de QA, sin red)."""

import pytest

from app.seed import HISTORY, seed
from tests.conftest import login


@pytest.fixture
def repo_id(client, settings) -> str:
    """Repo de demostración del usuario "ana" (el que inicia sesión en conftest)."""
    return seed("ana", settings)


def test_sin_repos(client):
    assert client.get("/api/repos").json() == []


def test_lista_de_repos(client, repo_id):
    [repo] = client.get("/api/repos").json()
    assert repo["id"] == repo_id and repo["name"] == "equipo/api-pagos"
    assert repo["status"] == "listo" and repo["files"] == 6
    assert repo["last_report_num"] == len(HISTORY) == repo["reports"]
    assert repo["last_report_id"] == f"{repo_id}-{len(HISTORY)}"


def test_historial_del_mas_reciente_al_mas_antiguo(client, repo_id):
    history = client.get(f"/api/repos/{repo_id}/history").json()
    assert [h["num"] for h in history] == [3, 2, 1]
    assert [h["created_at"] for h in history] == sorted((h["created_at"] for h in history), reverse=True)
    assert history[0]["languages"][0] == {"name": "Python", "files": 6}
    assert len(client.get(f"/api/repos/{repo_id}/history", params={"limit": 2}).json()) == 2


def test_seed_es_idempotente(client, repo_id, settings):
    assert seed("ana", settings) == repo_id
    assert len(client.get(f"/api/repos/{repo_id}/history").json()) == len(HISTORY)


def test_seed_requiere_usuario(settings):
    with pytest.raises(SystemExit):
        seed("nadie", settings)


def test_arbol(client, repo_id):
    tree = client.get(f"/api/repos/{repo_id}/tree").json()
    by_path = {e["path"]: e for e in tree}
    assert by_path["api.py"]["dir"] == "" and by_path["pagos/procesador.py"]["dir"] == "pagos"
    assert "requirements.txt" in by_path and "tests/test_procesador.py" in by_path
    assert [e["dir"] for e in tree] == sorted(e["dir"] for e in tree)


def test_leer_archivo(client, repo_id):
    body = client.get("/api/file", params={"repo": repo_id, "path": "requirements.txt"}).json()
    assert body["language"] == "plaintext" and "requests" in body["content"]


@pytest.mark.parametrize("path", ["../secreto.py", "/etc/passwd", "C:\\Windows\\win.ini", ".env"])
def test_rutas_no_validas(client, repo_id, path):
    assert client.get("/api/file", params={"repo": repo_id, "path": path}).status_code == 400


def test_otro_usuario_no_ve_el_repo(anon, fake, repo_id):
    # Otra cuenta de GitHub en un cliente sin la sesión de "ana"
    fake.user = fake.user.__class__(id=99, login="eve", name=None, email=None, avatar_url=None)
    login(anon)
    assert anon.get("/api/repos").json() == []
    assert anon.get(f"/api/repos/{repo_id}/history").status_code == 404
    assert anon.get(f"/api/repos/{repo_id}/tree").status_code == 404
    assert anon.get("/api/file", params={"repo": repo_id, "path": "api.py"}).status_code == 404


def test_requiere_sesion(anon):
    assert anon.get("/api/repos").status_code == 401
