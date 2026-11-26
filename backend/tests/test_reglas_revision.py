"""
Reglas de negocio al cargar el repo (Nuevo análisis): revisión sin clonar (POST /api/reglas/revisar), reglas
corregidas en el formulario (`rules` de /api/analyze) y su uso cuando el archivo del repo no es válido.
"""

import pytest

from app.analyses import reglas
from tests.test_analysis import URL, wait_done
from tests.test_reglas import REGLAS, ClonerConReglas, correr, regla, repo


@pytest.fixture
def cloner() -> ClonerConReglas:
    """El repo de conftest más reglas_negocio.toml (REGLAS) y app/pagos/cobro.py."""
    return ClonerConReglas()


INVALIDO = regla(severidad='"critica"')


def revisar(client, **body):
    return client.post("/api/reglas/revisar", json={"url": URL, "branch": "main", **body})


# ─── Motor: archivo del repo con errores y reglas corregidas en la app ───


def test_archivo_del_repo_invalido_usa_las_de_la_app(tmp_path):
    root, files = repo(tmp_path, {"reglas_negocio.toml": INVALIDO, "app/pagos/cobro.py": "x = float(1)\n"})
    check = reglas.run(root, files, lambda f: (root / f).read_text(encoding="utf-8").split("\n"), REGLAS)
    assert check.error is None and check.origin == "app" and check.source == reglas.APP_SOURCE and check.project == "Tienda"
    assert check.repo_error.startswith("reglas_negocio.toml: ") and "severidad" in check.repo_error
    assert check.results[0].status == "no_cumple"
    linea = reglas.summary_line(check)
    assert "aviso: reglas_negocio.toml: " in linea and "se usaron las reglas corregidas en la app" in linea


def test_archivo_valido_del_repo_gana_a_la_app(tmp_path):
    root, files = repo(tmp_path, {"reglas_negocio.toml": REGLAS})
    check = reglas.run(root, files, lambda f: (root / f).read_text(encoding="utf-8").split("\n"), regla())
    assert check.origin == "repo" and check.project == "Tienda" and check.repo_error is None


def test_archivo_invalido_sin_reglas_en_la_app_reporta_el_error(tmp_path):
    root, files = repo(tmp_path, {"docs/reglas_negocio.toml": INVALIDO})
    check = correr(root, files)
    assert check.source == "docs/reglas_negocio.toml" and "severidad" in check.error and check.repo_error is None


# ─── Revisión sin clonar ───


def test_revisar_repo_sin_reglas(client, fake):
    body = revisar(client).json()
    assert body["repo"] == "ana/api-pagos" and body["status"] == "missing" and body["file"] is None
    assert body["active"] is None and body["project_id"] is None and body["checked"] is None
    # Plantilla con el nombre del repo y sus carpetas con código
    assert 'nombre  = "ana/api-pagos"' in body["template"] and 'rutas       = ["app/"]' in body["template"]
    # Con el token del usuario
    assert fake.tree_tokens == ["gho_secreto123"]


def test_revisar_repo_con_reglas_validas(client, fake):
    fake.set_file("reglas_negocio.toml", REGLAS)
    body = revisar(client).json()
    assert body["status"] == "valid" and body["active"] == "repo"
    f = body["file"]
    assert f["path"] == "reglas_negocio.toml" and f["project"] == "Tienda" and len(f["rules"]) == 4 and f["content"] == REGLAS
    # `rutas` revisadas contra el árbol de la rama
    # Primero el aviso de `obligatorio` obsoleto (REGLAS es formato v1)
    assert f["warnings"][0].startswith("RN-002: `obligatorio` está obsoleto")
    assert f["warnings"][1:] == ["RN-002: la ruta `app/admin/` no existe en ana/api-pagos", "RN-004: la ruta `app/pago/` no existe en ana/api-pagos"]


def test_revisar_repo_con_reglas_invalidas(client, fake):
    fake.set_file("docs/reglas_negocio.toml", INVALIDO)
    body = revisar(client).json()
    assert body["status"] == "invalid" and body["active"] == "repo"
    assert body["file"]["path"] == "docs/reglas_negocio.toml" and body["file"]["valid"] is False
    assert "línea 4 · RN-001: `severidad` debe ser alta, media o baja" in body["file"]["error"]


def test_revisar_valida_el_contenido_del_formulario(client, fake):
    fake.set_file("reglas_negocio.toml", INVALIDO)
    ok = revisar(client, content=REGLAS.replace('["app/admin/"]', '["app/core/"]')).json()
    assert ok["checked"]["valid"] and ok["checked"]["warnings"][1:] == ["RN-004: la ruta `app/pago/` no existe en ana/api-pagos"]
    mal = revisar(client, content="[proyecto").json()["checked"]
    assert mal["valid"] is False and "TOML" in mal["error"]


def test_revisar_sin_acceso_no_bloquea(client):
    body = client.post("/api/reglas/revisar", json={"url": "https://github.com/ana/privado", "branch": "main"}).json()
    assert body["status"] == "unavailable" and "No se encontró el repositorio o la rama" in body["message"]
    assert body["file"] is None and body["template"]
    assert revisar(client, branch="develop").json()["status"] == "unavailable"


def test_revisar_reintenta_sin_token_revocado(client, fake):
    fake.reject_token = True
    fake.set_file("reglas_negocio.toml", REGLAS)
    assert revisar(client).json()["status"] == "valid"
    assert fake.tree_tokens == ["gho_secreto123", None]


def test_revisar_valida_url_y_rama(client):
    assert client.post("/api/reglas/revisar", json={"url": "https://gitlab.com/a/b"}).json()["error"]["code"] == "invalid_url"
    assert revisar(client, branch="-x").json()["error"]["code"] == "invalid_branch"
    assert client.post("/api/reglas/revisar", json={"url": URL}).status_code == 200


def test_revisar_requiere_sesion(anon):
    assert anon.post("/api/reglas/revisar", json={"url": URL}).status_code == 401


def test_revisar_proyecto_existente_con_reglas_en_la_app(client, fake, cloner):
    cloner.contenido = None
    rid = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])["repo_id"]
    client.put(f"/api/projects/{rid}/reglas", json={"content": REGLAS})
    fake.set_file("reglas_negocio.toml", INVALIDO)
    body = revisar(client).json()
    # El archivo del repo no es válido: el análisis usará las de la app
    assert body["project_id"] == rid and body["status"] == "invalid" and body["active"] == "app"
    assert body["uploaded"]["valid"] and body["uploaded"]["project"] == "Tienda"


# ─── Reglas corregidas en el formulario ───


def test_analizar_con_reglas_invalidas_responde_422_sin_crear_el_repo(client):
    res = client.post("/api/analyze", json={"url": URL, "rules": INVALIDO})
    assert res.status_code == 422 and res.json()["error"]["code"] == "invalid_rules" and "severidad" in res.json()["error"]["message"]
    assert client.get("/api/repos").json() == []


def test_analizar_con_reglas_corregidas_cuando_el_repo_tiene_errores(client, cloner):
    cloner.contenido = INVALIDO
    job = wait_done(client, client.post("/api/analyze", json={"url": URL, "rules": REGLAS}).json()["job_id"])
    assert job["status"] == "done"
    assert any("se usaron las reglas corregidas en la app" in line for line in job["logs"])
    body = client.get(f"/api/report/{job['report_id']}/reglas").json()
    assert body["origin"] == "app" and body["error"] is None and body["project"] == "Tienda" and body["summary"]["total"] == 4
    assert body["repo_error"].startswith("reglas_negocio.toml: ") and "severidad" in body["repo_error"]

    # Quedan guardadas en el proyecto: Configuración las muestra y dice que son las que se usan
    project = client.get(f"/api/projects/{job['repo_id']}/reglas").json()
    assert project["active"] == "app" and project["repo"]["valid"] is False and project["uploaded"]["content"] == REGLAS


def test_reporte_sin_reglas_corregidas_no_trae_repo_error(client):
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    assert client.get(f"/api/report/{job['report_id']}/reglas").json()["repo_error"] is None
