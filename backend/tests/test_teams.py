"""Equipos (app.teams): invitaciones, repos compartidos, salir, quitar y ceder el equipo."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.db import connect
from app.github.client import GithubUser
from app.seed import seed
from tests.test_analysis import URL, wait_done


@pytest.fixture
def other(client, fake):
    """Segunda persona (Beto), con su propia sesión sobre la misma app."""
    c = TestClient(client.app)
    c.__enter__()
    original = fake.user
    fake.user = GithubUser(id=77, login="beto", name="Beto Ruiz", email="beto@correo.dev", avatar_url=None)
    state = c.post("/api/auth/github/authorize").json()["state"]
    token = c.post("/api/auth/github/callback", json={"code": "buen-code", "state": state}).json()["token"]
    c.headers["Authorization"] = f"Bearer {token}"
    fake.user = original
    yield c
    c.__exit__(None, None, None)


def invite(client) -> str:
    res = client.post("/api/team/invites", headers={"Origin": "http://localhost:5173"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["url"] == f"http://localhost:5173/join/{body['code']}"
    return body["code"]


def test_cada_quien_empieza_con_su_equipo(client, other):
    me = client.get("/api/auth/me").json()
    assert me["team"] == {"name": "Equipo de Ana López", "members": 1}
    team = client.get("/api/team").json()
    assert team["role"] == "owner" and [m["login"] for m in team["members"]] == ["ana"]
    assert other.get("/api/team").json()["name"] == "Equipo de Beto Ruiz"


def test_repos_de_otro_equipo_son_invisibles(client, other, settings):
    repo_id = seed("ana", settings)
    assert other.get(f"/api/report/latest?repo={repo_id}").status_code == 404
    assert other.get("/api/repos").json() == []


def test_unirse_comparte_repos_y_analisis(client, other, settings):
    repo_id = seed("ana", settings)
    code = invite(client)
    preview = other.get(f"/api/team/invites/{code}").json()
    assert preview["team_name"] == "Equipo de Ana López" and preview["invited_by"] == "Ana López"
    assert preview["members"] == 1 and preview["conflicts"] == [] and preview["already_member"] is False

    team = other.post("/api/team/join", json={"code": code}).json()
    assert team["role"] == "member" and [m["login"] for m in team["members"]] == ["ana", "beto"]
    assert other.get("/api/auth/me").json()["team"] == {"name": "Equipo de Ana López", "members": 2}

    # Beto ve y analiza los repos del equipo; Ana ve lo que Beto agrega
    assert other.get(f"/api/report/latest?repo={repo_id}").status_code == 200
    job = wait_done(other, other.post("/api/analyze", json={"url": URL}).json()["job_id"])
    assert job["status"] == "done"
    assert "ana/api-pagos" in {r["name"] for r in client.get("/api/repos").json()}
    assert len(client.get("/api/repos").json()) == 2
    assert client.get(f"/api/jobs/{job['id']}").status_code == 200


def test_conflicto_de_nombres_al_unirse(client, other):
    wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    wait_done(other, other.post("/api/analyze", json={"url": URL}).json()["job_id"])
    code = invite(client)
    assert other.get(f"/api/team/invites/{code}").json()["conflicts"] == ["ana/api-pagos"]
    other.post("/api/team/join", json={"code": code})
    # Queda una sola copia: la del equipo
    [repo] = other.get("/api/repos").json()
    assert repo["id"] == client.get("/api/repos").json()[0]["id"]


def test_solo_el_dueno_invita_y_renombra(client, other):
    other.post("/api/team/join", json={"code": invite(client)})
    assert other.post("/api/team/invites").status_code == 403
    assert other.patch("/api/team", json={"name": "Otro"}).status_code == 403
    assert client.patch("/api/team", json={"name": "Backend"}).json()["name"] == "Backend"
    assert other.get("/api/auth/me").json()["team"]["name"] == "Backend"


def test_salir_del_equipo(client, other, settings):
    repo_id = seed("ana", settings)
    other.post("/api/team/join", json={"code": invite(client)})
    # El dueño no puede irse dejando miembros
    res = client.delete("/api/team/members/me")
    assert res.status_code == 409 and res.json()["error"]["code"] == "owner_must_transfer"

    team = other.delete("/api/team/members/me").json()
    assert team["name"] == "Equipo de Beto Ruiz" and team["role"] == "owner" and team["repos"] == 0
    assert other.get(f"/api/report/latest?repo={repo_id}").status_code == 404
    assert len(client.get("/api/team").json()["members"]) == 1


def test_quitar_y_ceder(client, other):
    other.post("/api/team/join", json={"code": invite(client)})
    beto = other.get("/api/auth/me").json()["id"]
    team = client.post(f"/api/team/members/{beto}/owner").json()
    assert {m["login"]: m["role"] for m in team["members"]} == {"ana": "member", "beto": "owner"}
    ana = client.get("/api/auth/me").json()["id"]
    assert client.delete(f"/api/team/members/{beto}").status_code == 403
    team = other.delete(f"/api/team/members/{ana}").json()
    assert [m["login"] for m in team["members"]] == ["beto"]
    assert client.get("/api/team").json()["name"] == "Equipo de Ana López"


def test_invitacion_vencida_o_inexistente(client, other, settings):
    code = invite(client)
    conn = connect(settings.database_path)
    conn.execute("UPDATE team_invites SET expires_at = ? WHERE code = ?", ((datetime.now(UTC) - timedelta(minutes=1)).isoformat(), code))
    conn.commit()
    assert other.post("/api/team/join", json={"code": code}).status_code == 410
    assert other.get("/api/team/invites/nada").status_code == 404


def test_migracion_de_bases_sin_equipos(tmp_path):
    """Una base anterior (repos con UNIQUE user_id, name) pasa a equipos sin perder reportes."""
    import sqlite3

    path = tmp_path / "vieja.db"
    old = sqlite3.connect(path)
    old.executescript(
        """
        CREATE TABLE users (id TEXT PRIMARY KEY, github_id INTEGER NOT NULL UNIQUE, login TEXT NOT NULL, name TEXT NOT NULL,
            email TEXT NOT NULL DEFAULT '', avatar_url TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE repos (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, url TEXT NOT NULL, branch TEXT NOT NULL,
            files INTEGER NOT NULL, status TEXT NOT NULL, error TEXT, created_at TEXT NOT NULL, UNIQUE (user_id, name));
        CREATE TABLE reports (id TEXT PRIMARY KEY, repo_id TEXT NOT NULL REFERENCES repos (id) ON DELETE CASCADE, num INTEGER NOT NULL,
            branch TEXT NOT NULL, commit_sha TEXT NOT NULL, created_at TEXT NOT NULL, duration_s INTEGER NOT NULL, seg INTEGER NOT NULL,
            test INTEGER NOT NULL, prac INTEGER NOT NULL, seed INTEGER NOT NULL, UNIQUE (repo_id, num));
        INSERT INTO users (id, github_id, login, name) VALUES ('u1', 1, 'ana', 'Ana');
        INSERT INTO repos VALUES ('r1', 'u1', 'ana/x', 'https://github.com/ana/x', 'main', 3, 'listo', NULL, '2026-01-01');
        INSERT INTO reports VALUES ('r1-1', 'r1', 1, 'main', 'abc', '2026-01-01', 10, 80, 70, 90, 1);
        """
    )
    old.close()
    conn = connect(str(path))
    repo = conn.execute("SELECT * FROM repos").fetchone()
    member = conn.execute("SELECT * FROM team_members WHERE user_id = 'u1'").fetchone()
    assert repo["team_id"] == member["team_id"] and member["role"] == "owner"
    assert conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 1
    # La cascada sigue apuntando a la tabla nueva
    conn.execute("DELETE FROM repos WHERE id = 'r1'")
    assert conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 0
