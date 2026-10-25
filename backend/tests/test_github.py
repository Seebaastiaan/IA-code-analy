def test_estado_conectado_tras_login(client):
    assert client.get("/api/github/status").json() == {"connected": True, "login": "ana", "avatar_url": "https://avatars/ana.png"}


def test_repos_y_busqueda(client):
    repos = client.get("/api/github/repos").json()
    assert [r["full_name"] for r in repos] == ["ana/api-pagos", "ana/dotfiles"]
    assert repos[1]["pushed_at"] == "2026-09-01T00:00:00Z"
    assert [r["full_name"] for r in client.get("/api/github/repos", params={"q": "PAGOS"}).json()] == ["ana/api-pagos"]


def test_token_revocado_responde_409_sin_cerrar_sesion(client, fake):
    fake.revoked = True
    res = client.get("/api/github/repos")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "github_not_connected"
    assert client.get("/api/github/status").json()["connected"] is False
    # La sesión de la app sigue viva
    assert client.get("/api/auth/me").status_code == 200


def test_ramas(client):
    assert client.get("/api/github/repos/ana/api-pagos/branches").json() == [{"name": "main"}, {"name": "develop"}]
    assert client.get("/api/github/repos/ana/otro/branches").status_code == 404
    assert client.get("/api/github/repos/ana/mal%20nombre/branches").status_code == 422
