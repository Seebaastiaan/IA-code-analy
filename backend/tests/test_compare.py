"""Comparativa: GET /api/repos/{id}/analyses y POST /api/diff (sobre los 4 análisis de app.seed)."""

import pytest

from app.seed import seed
from tests.conftest import login


@pytest.fixture
def repo_id(client, settings) -> str:
    return seed("ana", settings)


@pytest.fixture
def ids(client, repo_id) -> list[str]:
    """Ids de los análisis, del más reciente (#4) al más antiguo (#1)."""
    return [o["id"] for o in client.get(f"/api/repos/{repo_id}/analyses").json()]


def diff(client, base: str, target: str):
    return client.post("/api/diff", json={"base": base, "target": target})


def test_opciones_del_mas_reciente_al_mas_antiguo(client, repo_id):
    opts = client.get(f"/api/repos/{repo_id}/analyses").json()
    assert [o["id"] for o in opts] == [f"{repo_id}-{n}" for n in (4, 3, 2, 1)]
    assert opts[0]["label"].startswith("#4 · ") and opts[0]["label"].endswith(" · main")


def test_detecta_resueltos(client, ids):
    res = diff(client, ids[3], ids[0])  # #1 → #4: el seed corrige hallazgos semana a semana
    assert res.status_code == 200
    body = res.json()
    assert body["new"] == []
    assert len(body["resolved"]) > 0
    assert all(f["status"] == "resolved" for f in body["resolved"])
    assert body["b"]["global"] > body["a"]["global"]


def test_es_simetrico(client, ids):
    ida, vuelta = diff(client, ids[3], ids[0]).json(), diff(client, ids[0], ids[3]).json()
    assert sorted((f["tool"], f["rule"], f["file"]) for f in ida["resolved"]) == sorted((f["tool"], f["rule"], f["file"]) for f in vuelta["new"])
    assert vuelta["resolved"] == []
    assert (ida["a"], ida["b"]) == (vuelta["b"], vuelta["a"])


def test_nuevos_llevan_ids_del_reporte_b(client, ids):
    body = diff(client, ids[0], ids[3]).json()  # #4 → #1: lo corregido "reaparece"
    ids_b = {f["id"] for f in client.get(f"/api/report/{ids[3]}").json()["findings"]}
    assert body["new"] and {f["id"] for f in body["new"]} <= ids_b


def test_mismo_analisis_sin_diferencias(client, ids):
    body = diff(client, ids[0], ids[0]).json()
    assert body["new"] == [] and body["resolved"] == [] and body["a"] == body["b"]


def test_scores_iguales_al_reporte(client, ids):
    body = diff(client, ids[1], ids[0]).json()
    assert body["a"] == client.get(f"/api/report/{ids[1]}").json()["scores"]
    assert body["b"] == client.get(f"/api/report/{ids[0]}").json()["scores"]


def test_respeta_reglas_ignoradas(client, repo_id, ids):
    rules = {f["rule"] for f in diff(client, ids[3], ids[0]).json()["resolved"]}
    assert rules
    cfg = client.get(f"/api/projects/{repo_id}/config").json()
    client.put(f"/api/projects/{repo_id}/config", json={**cfg, "ignored": sorted(rules)})
    assert diff(client, ids[3], ids[0]).json()["resolved"] == []


def test_sin_codigo_en_la_respuesta(client, ids):
    body = diff(client, ids[3], ids[0]).json()
    assert all(f["snippet"] is None for f in body["resolved"])


@pytest.mark.parametrize("base", ["no-existe-1", "branch:main", " "])
def test_analisis_inexistente(client, ids, base):
    assert diff(client, base, ids[0]).status_code in (404, 422)


def test_otro_usuario_no_ve_nada(client, anon, fake, repo_id, ids):
    fake.user = fake.user.__class__(id=99, login="beto", name=None, email=None, avatar_url=None)
    login(anon)
    assert anon.get(f"/api/repos/{repo_id}/analyses").status_code == 404
    res = diff(anon, ids[1], ids[0])
    assert res.status_code == 404
    assert "seg" not in res.text


def test_repos_distintos(client, settings, ids):
    # Segundo repo del mismo usuario con un análisis propio
    from app.analyses.models import ReportInput
    from app.analyses.store import AnalysisStore
    from app.db import connect

    conn = connect(settings.database_path)
    store = AnalysisStore(conn)
    user_id = store.repo(ids[0].rsplit("-", 1)[0])["user_id"]
    otro = store.upsert_repo(user_id, "ana/otro", "https://github.com/ana/otro", "main")
    rid, _ = store.save_report(otro, ReportInput(branch="main", commit="abc1234", duration_s=1, coverage_total=80, tests_failed=0, avg_complexity=2))
    conn.close()
    res = diff(client, ids[0], rid)
    assert res.status_code == 422 and res.json()["error"]["code"] == "different_repos"


def test_requiere_sesion(anon):
    assert anon.post("/api/diff", json={"base": "a-1", "target": "a-2"}).status_code == 401
