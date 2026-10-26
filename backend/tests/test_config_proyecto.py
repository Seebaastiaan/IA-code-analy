"""Configuración del proyecto: /api/projects/{id}/config y .ia_voy.toml."""

import tomllib

import pytest

from app.analyses.config_file import ConfigError, from_toml, normalize, to_toml
from app.analyses.store import ProjectConfig, default_config
from app.analyses.workspace import Workspace
from app.seed import seed
from tests.conftest import login
from tests.test_analysis import URL, wait_done

CONFIG = {"weights": {"seg": 40, "test": 40, "prac": 20}, "thresholds": {"score": 80, "cov": 70}, "ignored": ["B101", "E722"], "excluded": ["migrations/"]}


@pytest.fixture
def repo_id(client, settings) -> str:
    return seed("ana", settings)


def url(repo_id: str) -> str:
    return f"/api/projects/{repo_id}/config"


def report(client, repo_id: str) -> dict:
    return client.get("/api/report/latest", params={"repo": repo_id}).json()


def test_valores_por_defecto(client, repo_id):
    assert client.get(url(repo_id)).json() == {
        "weights": {"seg": 50, "test": 30, "prac": 20},
        "thresholds": {"score": 70, "cov": 60},
        "ignored": ["B101"],
        "excluded": ["migrations/", "tests/fixtures/"],
    }


def test_guardar_y_leer(client, repo_id):
    res = client.put(url(repo_id), json=CONFIG)
    assert res.status_code == 200 and res.json() == CONFIG
    assert client.get(url(repo_id)).json() == CONFIG


def test_normaliza_listas_y_rutas(client, repo_id):
    body = {**CONFIG, "ignored": [" E722 ", "E722", "", "requests 2.25.1"], "excluded": ["./scripts/", "\\docs\\", "/build", "scripts/"]}
    saved = client.put(url(repo_id), json=body).json()
    assert saved["ignored"] == ["E722", "requests 2.25.1"]
    assert saved["excluded"] == ["scripts/", "docs/", "build"]


@pytest.mark.parametrize(
    "change",
    [
        {"weights": {"seg": 0, "test": 0, "prac": 0}},
        {"weights": {"seg": 120, "test": 0, "prac": 0}},
        {"thresholds": {"score": -1, "cov": 60}},
        {"excluded": ["../fuera/"]},
        {"excluded": ["C:/Windows/"]},
        {"ignored": ["x" * 201]},
    ],
)
def test_validaciones(client, repo_id, change):
    res = client.put(url(repo_id), json={**CONFIG, **change})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "invalid_config"


def test_body_incompleto(client, repo_id):
    assert client.put(url(repo_id), json={"weights": CONFIG["weights"]}).status_code == 422


def test_ignorar_regla_se_aplica_al_instante(client, repo_id):
    before = report(client, repo_id)
    assert any(f["rule"] == "B602" for f in before["findings"])
    cfg = client.get(url(repo_id)).json()
    client.put(url(repo_id), json={**cfg, "ignored": [*cfg["ignored"], "B602"]})
    after = report(client, repo_id)
    assert not any(f["rule"] == "B602" for f in after["findings"])
    # B602 es de severidad alta en seguridad: el score sube
    assert after["scores"]["seg"] > before["scores"]["seg"]
    assert after["scores"]["global"] > before["scores"]["global"]


def test_pesos_y_umbrales_en_reporte_y_tablero(client, repo_id):
    client.put(url(repo_id), json=CONFIG)
    rep = report(client, repo_id)
    assert rep["weights"] == CONFIG["weights"] and rep["thresholds"] == CONFIG["thresholds"]
    s = rep["scores"]
    assert s["global"] == round((40 * s["seg"] + 40 * s["test"] + 20 * s["prac"]) / 100, 1)
    assert client.get("/api/dashboard").json()["thresholds"] == CONFIG["thresholds"]


def test_rutas_excluidas_salen_del_reporte_y_del_arbol(client, repo_id):
    client.put(url(repo_id), json={**CONFIG, "excluded": ["api.py", "pagos/"]})
    files = {f["file"] for f in report(client, repo_id)["findings"]}
    assert "api.py" not in files and not any(f.startswith("pagos/") for f in files)
    tree = {e["path"] for e in client.get(f"/api/repos/{repo_id}/tree").json()}
    assert "api.py" not in tree and "pagos/procesador.py" not in tree and "auth.py" in tree


def test_escribe_ia_voy_toml_en_el_clon(client, repo_id, settings):
    client.put(url(repo_id), json=CONFIG)
    data = tomllib.loads((Workspace(settings, repo_id).root / ".ia_voy.toml").read_text(encoding="utf-8"))
    assert data["pesos"] == {"seguridad": 0.4, "pruebas": 0.4, "practicas": 0.2}
    assert data["umbrales"] == {"score_minimo": 80, "cobertura_minima": 70}
    assert data["reglas"]["ignorar"] == ["B101", "E722"] and data["rutas"]["excluir"] == ["migrations/"]


def test_otro_usuario_no_ve_la_configuracion(client, anon, fake, repo_id):
    fake.user = fake.user.__class__(id=99, login="eve", name=None, email=None, avatar_url=None)
    login(anon)
    assert anon.get(url(repo_id)).status_code == 404
    assert anon.put(url(repo_id), json=CONFIG).status_code == 404


def test_requiere_sesion(anon, repo_id):
    # `client` (que usa repo_id) es este mismo cliente con sesión: se le quita
    anon.headers.pop("Authorization")
    assert anon.get(url(repo_id)).status_code == 401


# ─── .ia_voy.toml ───


def test_toml_ida_y_vuelta():
    cfg = normalize(ProjectConfig(**CONFIG))
    assert from_toml(to_toml(cfg), default_config()) == cfg


def test_toml_parcial_completa_con_la_base():
    cfg = from_toml('[reglas]\nignorar = ["S101"]\n', default_config())
    assert cfg.ignored == ["S101"] and cfg.weights == default_config().weights


@pytest.mark.parametrize("text", ["no es toml [", "[reglas]\nignorar = 'S101'\n", "[pesos]\nseguridad = 0\npruebas = 0\npracticas = 0\n"])
def test_toml_invalido(text):
    with pytest.raises(ConfigError):
        from_toml(text, default_config())


def test_primer_analisis_adopta_el_toml_del_repo(client, cloner, monkeypatch):
    original = cloner.clone

    def clone_with_config(settings, repo_id, url, branch, token, attempt):
        result = original(settings, repo_id, url, branch, token, attempt)
        from app.analysis import clone as clone_mod

        tmp = clone_mod.clones_root(settings) / f"{repo_id}.tmp-{attempt}"
        (tmp / ".ia_voy.toml").write_text('[pesos]\nseguridad = 0.6\npruebas = 0.2\npracticas = 0.2\n\n[reglas]\nignorar = ["E501"]\n', encoding="utf-8")
        return result

    monkeypatch.setattr(cloner, "clone", clone_with_config)
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    cfg = client.get(url(job["repo_id"])).json()
    assert cfg["weights"] == {"seg": 60, "test": 20, "prac": 20} and cfg["ignored"] == ["E501"]
    # Después manda lo guardado desde la pantalla, aunque el repo traiga su archivo
    client.put(url(job["repo_id"]), json=CONFIG)
    wait_done(client, client.post(f"/api/repos/{job['repo_id']}/analyze").json()["job_id"])
    assert client.get(url(job["repo_id"])).json() == CONFIG
