"""Compartir: POST /api/report/{id}/share y la vista pública /api/public/r/{id} (sobre los análisis de app.seed)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.seed import seed


@pytest.fixture
def report_id(client, settings) -> str:
    repo_id = seed("ana", settings)
    return client.get(f"/api/report/latest?repo={repo_id}").json()["id"]


def share(client, report_id: str, **body):
    return client.post(f"/api/report/{report_id}/share", json={"password": None, "expires_days": 7, "include_code": False, **body})


def public(client, share_id: str, token: str | None = None):
    """Petición sin sesión, como la haría un invitado."""
    auth = client.headers.pop("Authorization", None)
    try:
        return client.get(f"/api/public/r/{share_id}", params={"token": token} if token else None)
    finally:
        if auth:
            client.headers["Authorization"] = auth


def unlock(client, share_id: str, password: str):
    return client.post(f"/api/public/r/{share_id}/unlock", json={"password": password})


def test_crea_enlace_con_expiracion(client, report_id):
    res = share(client, report_id, expires_days=7)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["url"] == f"http://localhost:5173/r/{body['share_id']}"
    expira = datetime.fromisoformat(body["expires_at"])
    assert timedelta(days=6, hours=23) < expira - datetime.now(UTC) <= timedelta(days=7)


def test_enlace_usa_el_origen_de_la_peticion(client, report_id):
    res = client.post(f"/api/report/{report_id}/share", json={"expires_days": 0, "include_code": False}, headers={"Origin": "https://ia-voy.trycloudflare.com"})
    body = res.json()
    assert body["url"].startswith("https://ia-voy.trycloudflare.com/r/")
    assert body["expires_at"] is None


def test_vista_publica_sin_sesion(client, report_id):
    share_id = share(client, report_id).json()["share_id"]
    res = public(client, share_id)
    assert res.status_code == 200, res.text
    body = res.json()
    report = client.get(f"/api/report/{report_id}").json()
    assert body["repo_name"] == report["repo_name"] and body["scores"] == report["scores"]
    assert body["shared_by"] == "Ana López"
    assert body["findings"], "el seed tiene hallazgos de severidad alta y media"
    assert all(f["sev"] in ("alta", "media") and f["status"] == "open" for f in body["findings"])
    assert all(f["snippet"] is None for f in body["findings"])
    assert body["include_code"] is False


def test_incluye_codigo_si_se_pide(client, report_id):
    share_id = share(client, report_id, include_code=True).json()["share_id"]
    body = public(client, share_id).json()
    assert body["include_code"] is True
    assert any(f["snippet"] for f in body["findings"])


def test_respeta_reglas_ignoradas(client, report_id):
    share_id = share(client, report_id).json()["share_id"]
    rule = public(client, share_id).json()["findings"][0]["rule"]
    repo_id = report_id.rsplit("-", 1)[0]
    cfg = client.get(f"/api/projects/{repo_id}/config").json()
    client.put(f"/api/projects/{repo_id}/config", json={**cfg, "ignored": [rule]})
    assert all(f["rule"] != rule for f in public(client, share_id).json()["findings"])


def test_con_contrasena(client, report_id):
    share_id = share(client, report_id, password="s3creta").json()["share_id"]
    assert public(client, share_id).status_code == 401
    assert public(client, share_id, token="123.falso").status_code == 401

    mal = unlock(client, share_id, "otra")
    assert mal.status_code == 403 and mal.json()["error"]["code"] == "wrong_password"

    token = unlock(client, share_id, "s3creta").json()["token"]
    assert public(client, share_id, token).status_code == 200
    # El token es de este enlace: no abre otro con contraseña
    otro = share(client, report_id, password="s3creta").json()["share_id"]
    assert public(client, otro, token).status_code == 401


def test_contrasena_no_se_guarda_en_claro(client, report_id, settings):
    from app.db import connect

    share_id = share(client, report_id, password="s3creta").json()["share_id"]
    row = connect(settings.database_path).execute("SELECT password_hash FROM shares WHERE id = ?", (share_id,)).fetchone()
    assert "s3creta" not in row["password_hash"]


def test_bloquea_fuerza_bruta(client, report_id):
    share_id = share(client, report_id, password="s3creta").json()["share_id"]
    for _ in range(10):
        assert unlock(client, share_id, "no").status_code == 403
    res = unlock(client, share_id, "s3creta")
    assert res.status_code == 429


def test_enlace_inexistente_y_expirado(client, report_id, settings):
    from app.db import connect

    assert public(client, "no-existe").status_code == 404
    share_id = share(client, report_id, expires_days=1).json()["share_id"]
    conn = connect(settings.database_path)
    conn.execute("UPDATE shares SET expires_at = ? WHERE id = ?", ((datetime.now(UTC) - timedelta(minutes=1)).isoformat(), share_id))
    conn.commit()
    res = public(client, share_id)
    assert res.status_code == 410 and res.json()["error"]["code"] == "expired"


def test_no_comparte_reportes_ajenos(client):
    assert share(client, "r-ajeno-1").status_code == 404


def test_requiere_sesion_para_compartir(client, report_id):
    auth = client.headers.pop("Authorization")
    try:
        assert share(client, report_id).status_code == 401
    finally:
        client.headers["Authorization"] = auth


def test_expiracion_invalida(client, report_id):
    assert share(client, report_id, expires_days=3).status_code == 422
