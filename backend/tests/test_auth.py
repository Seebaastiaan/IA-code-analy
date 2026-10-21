import sqlite3

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app
from tests.conftest import GH_TOKEN, login


def test_authorize_devuelve_url_y_state(anon):
    body = anon.post("/api/auth/github/authorize").json()
    assert "client_id=cid" in body["url"]
    assert f"state={body['state']}" in body["url"]


def test_login_crea_usuario_y_guarda_token_cifrado(anon, settings):
    body = login(anon)
    assert body["user"]["login"] == "ana"
    assert body["user"]["name"] == "Ana López"
    assert body["user"]["initials"] == "AL"
    assert body["user"]["email"] == "ana@correo.dev"
    assert anon.get("/api/auth/me").json()["id"] == body["user"]["id"]

    raw = sqlite3.connect(settings.database_path).execute("SELECT token_enc FROM github_accounts").fetchone()[0]
    assert GH_TOKEN not in raw
    assert Fernet(settings.token_encryption_key).decrypt(raw.encode()).decode() == GH_TOKEN


def test_segundo_login_reutiliza_el_usuario(anon, fake):
    first = login(anon)["user"]["id"]
    fake.user.name = "Ana L."
    second = login(anon)["user"]
    assert second["id"] == first
    assert second["name"] == "Ana L."


def test_state_invalido_o_reutilizado(anon):
    res = anon.post("/api/auth/github/callback", json={"code": "buen-code", "state": "inventado"})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "invalid_state"

    state = anon.post("/api/auth/github/authorize").json()["state"]
    assert anon.post("/api/auth/github/callback", json={"code": "buen-code", "state": state}).status_code == 200
    assert anon.post("/api/auth/github/callback", json={"code": "buen-code", "state": state}).status_code == 400


def test_code_rechazado_por_github(anon):
    state = anon.post("/api/auth/github/authorize").json()["state"]
    res = anon.post("/api/auth/github/callback", json={"code": "malo", "state": state})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "github_oauth_failed"


def test_rutas_privadas_requieren_sesion(anon):
    assert anon.get("/api/auth/me").status_code == 401
    assert anon.get("/api/repos").json()["error"]["code"] == "unauthorized"


def test_token_alterado_rechazado(client):
    token = client.headers["Authorization"].removeprefix("Bearer ")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}x"}).status_code == 401


def test_body_invalido_usa_formato_de_error(anon):
    res = anon.post("/api/auth/github/callback", json={"code": "x"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "invalid_request"


def test_sin_oauth_app_configurada(settings):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings.model_copy(update={"github_client_id": ""})
    res = TestClient(app).post("/api/auth/github/authorize")
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "github_not_configured"


def test_state_vencido(anon, settings):
    from app.db import connect

    state = anon.post("/api/auth/github/authorize").json()["state"]
    conn = connect(settings.database_path)
    conn.execute("UPDATE oauth_states SET expires_at = 0 WHERE state = ?", (state,))
    conn.commit()
    res = anon.post("/api/auth/github/callback", json={"code": "buen-code", "state": state})
    assert res.status_code == 400 and res.json()["error"]["code"] == "invalid_state"
