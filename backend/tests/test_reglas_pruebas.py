"""
Reglas de negocio, Sprint 8 (ADR-003 §5): nivel pruebas (plugin ia_voy_reglas y lectura de las pruebas),
estado combinado con el patrón y reglas cargadas desde Configuración.
"""

import json
import sqlite3
from pathlib import Path

import pytest

from app.analyses import reglas
from app.analyses.reglas import LinkedTest, RuleResult, combine, linked_in_source, parse, with_tests
from app.analyses.store import default_config
from app.analysis import pipeline, sandbox
from app.db import connect
from tests.conftest import login
from tests.test_analysis import URL, wait_done
from tests.test_reglas import ClonerConReglas, correr, regla, repo

pytest_plugins = ["pytester"]

PLUGIN_DIR = Path(sandbox.PLUGIN).parent


# ─── Plugin de pytest (corre en el sandbox) ───


@pytest.fixture
def run_plugin(pytester, monkeypatch, tmp_path):
    """Corre pytest con -p ia_voy_reglas sobre los archivos dados y devuelve (resultado, pruebas por nodeid)."""
    out = tmp_path / "reglas.json"
    monkeypatch.setenv("IA_VOY_REGLAS_OUT", str(out))
    pytester.syspathinsert(PLUGIN_DIR)

    def run(*args: str, **files: str):
        pytester.makepyfile(**files)
        result = pytester.runpytest("-p", "ia_voy_reglas", "-p", "no:cacheprovider", *args)
        data = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else None
        return result, {t["nodeid"].split("::", 1)[1]: t for t in (data or {}).get("tests", [])}

    return run


PRUEBAS = '''
import pytest

pytestmark = pytest.mark.regla("RN-009")


@pytest.mark.regla("RN-001", "rn-002")
def test_pasa():
    assert True


@pytest.mark.regla("RN-001")
def test_falla():
    assert 1 == 2, "uno no es dos"


def test_rn003_por_nombre():
    pass


@pytest.fixture
def roto():
    raise RuntimeError("fixture rota")


@pytest.mark.regla("RN-004")
def test_error_en_fixture(roto):
    pass


@pytest.mark.regla("RN-005")
@pytest.mark.skip(reason="todavía no")
def test_omitida():
    pass


@pytest.mark.regla("RN-006")
class TestClase:
    def test_metodo(self):
        pass
'''


def test_plugin_registra_pruebas_y_resultados(run_plugin):
    # makepyfile quita la primera línea vacía: test_falla (su decorador) queda en la línea 11
    result, tests = run_plugin("--strict-markers", test_tienda=PRUEBAS)
    # --strict-markers no falla: el plugin registra el marcador
    result.assert_outcomes(passed=3, failed=1, errors=1, skipped=1)
    assert tests["test_pasa"]["rules"] == ["RN-001", "RN-002", "RN-009"] and tests["test_pasa"]["outcome"] == "passed"
    assert tests["test_falla"]["outcome"] == "failed" and "uno no es dos" in tests["test_falla"]["message"]
    assert tests["test_falla"]["file"] == "test_tienda.py" and tests["test_falla"]["line"] == 11
    assert tests["test_rn003_por_nombre"]["rules"] == ["RN-003", "RN-009"]
    assert tests["test_error_en_fixture"]["outcome"] == "error" and "fixture rota" in tests["test_error_en_fixture"]["message"]
    assert tests["test_omitida"]["outcome"] == "skipped"
    assert tests["TestClase::test_metodo"]["rules"] == ["RN-006", "RN-009"]


def test_plugin_sin_pruebas_ligadas_escribe_lista_vacia(run_plugin):
    result, tests = run_plugin(test_x="def test_a():\n    pass\n")
    result.assert_outcomes(passed=1)
    assert tests == {}


def test_plugin_respeta_deseleccion(run_plugin):
    _, tests = run_plugin("-k", "pasa", test_tienda=PRUEBAS)
    assert set(tests) == {"test_pasa"}


def test_el_sandbox_carga_el_plugin():
    assert "-p ia_voy_reglas" in sandbox.SCRIPT and '"$OUT/plugins' in sandbox.SCRIPT
    assert sandbox.PLUGIN.is_file()
    # No depende del backend: corre con las dependencias del repo analizado
    assert "from app" not in sandbox.PLUGIN.read_text(encoding="utf-8")


# ─── Pruebas leídas del código (sin sandbox) ───


def test_lee_las_pruebas_ligadas_sin_ejecutarlas():
    found = {t.name: t for t in linked_in_source("tests/test_tienda.py", PRUEBAS)}
    assert set(found) == {f"tests/test_tienda.py::{n}" for n in ("test_pasa", "test_falla", "test_rn003_por_nombre", "test_error_en_fixture", "test_omitida", "TestClase::test_metodo")}
    assert found["tests/test_tienda.py::test_pasa"].rules == ("RN-001", "RN-002", "RN-009")
    assert found["tests/test_tienda.py::test_falla"].line == 12
    assert all(t.outcome == "sin_ejecutar" for t in found.values())
    # Un archivo con errores de sintaxis no rompe nada
    assert linked_in_source("tests/test_roto.py", "def test_(:\n") == []


# ─── Estado combinado ───


def resultado(status: str = "cumple", level: str = "patron") -> RuleResult:
    rule = parse(regla()).rules[0]
    return RuleResult(rule, status, level, "detalle del patrón")


def prueba(outcome: str, name: str = "t") -> LinkedTest:
    return LinkedTest(name=name, file="tests/test_x.py", line=1, rules=("RN-001",), outcome=outcome)


@pytest.mark.parametrize(("patron", "pruebas", "motivo", "estado", "nivel"), [
    (None, [prueba("passed")], None, "cumple", "pruebas"),
    (None, [prueba("passed"), prueba("failed", "u")], None, "no_cumple", "pruebas"),
    (None, [prueba("error")], None, "no_cumple", "pruebas"),
    (None, [prueba("skipped")], None, "sin_verificar", "pruebas"),
    (None, [prueba("sin_ejecutar")], "sandbox apagado", "sin_verificar", "pruebas"),
    (None, [], None, "sin_verificar", "ninguno"),
    ("cumple", [prueba("passed")], None, "cumple", "pruebas_y_patron"),
    ("no_cumple", [prueba("passed")], None, "no_cumple", "pruebas_y_patron"),
    # Sin ejecutar sus pruebas no se puede decir que cumple
    ("cumple", [prueba("sin_ejecutar")], "sandbox apagado", "sin_verificar", "pruebas_y_patron"),
    ("no_cumple", [prueba("sin_ejecutar")], "sandbox apagado", "no_cumple", "pruebas_y_patron"),
    ("cumple", [], None, "cumple", "patron"),
])
def test_combina_patron_y_pruebas(patron, pruebas, motivo, estado, nivel):
    base = resultado(patron, "patron") if patron else resultado("sin_verificar", "ninguno")
    r = combine(base, pruebas, motivo)
    assert (r.status, r.level) == (estado, nivel)
    if motivo:
        assert motivo in r.detail
    if nivel == "ninguno":
        assert '@pytest.mark.regla("RN-001")' in r.detail and "test_rn001_" in r.detail
    # Las que fallan van primero
    if any(t.outcome == "failed" for t in pruebas):
        assert r.tests[0].outcome == "failed"


REGLAS = '''
[proyecto]
nombre = "Tienda"

[[regla]]
id = "RN-001"
titulo = "Montos con Decimal"
descripcion = "Nunca float."
severidad = "alta"
rutas = ["app/"]
prohibido = 'float\\('

[[regla]]
id = "RN-002"
titulo = "Cancelado no vuelve a pagado"
descripcion = "Se verifica con pruebas."
severidad = "alta"
'''

TEST_PEDIDOS = '''
import pytest


@pytest.mark.regla("RN-002")
def test_cancelado_no_vuelve_a_pagado():
    pass


@pytest.mark.regla("RN-099")
def test_regla_que_no_existe():
    pass
'''


def test_sin_sandbox_las_pruebas_quedan_sin_ejecutar(tmp_path):
    root, files = repo(tmp_path, {"reglas_negocio.toml": REGLAS, "app/cobro.py": "x = 1\n", "tests/test_pedidos.py": TEST_PEDIDOS})
    check = with_tests(correr(root, files), None, "sin sandbox")
    r1, r2 = check.results
    assert (r1.status, r1.level) == ("cumple", "patron")
    assert (r2.status, r2.level) == ("sin_verificar", "pruebas") and "sin sandbox" in r2.detail
    assert r2.tests[0].name == "tests/test_pedidos.py::test_cancelado_no_vuelve_a_pagado"
    assert check.warnings == ["tests/test_pedidos.py::test_regla_que_no_existe usa RN-099, que no está en reglas_negocio.toml"]
    assert check.tests_ran is False
    line = reglas.summary_line(check)
    assert "2 prueba(s) ligada(s) sin ejecutar" not in line and "1 prueba(s) ligada(s) sin ejecutar" in line
    assert "aviso: tests/test_pedidos.py::test_regla_que_no_existe usa RN-099" in line


def test_con_el_resultado_del_plugin(tmp_path):
    root, files = repo(tmp_path, {"reglas_negocio.toml": REGLAS, "app/cobro.py": "x = 1\n"})
    data = {"version": 1, "tests": [
        {"nodeid": "tests/test_p.py::test_a", "file": "tests/test_p.py", "line": 4, "rules": ["RN-002"], "outcome": "passed", "message": ""},
        {"nodeid": "tests/test_p.py::test_b", "file": "tests/test_p.py", "line": 9, "rules": ["RN-002", "RN-01"], "outcome": "failed", "message": "assert False"},
    ]}
    check = with_tests(correr(root, files), data, None)
    r2 = check.results[1]
    assert (r2.status, r2.level) == ("no_cumple", "pruebas") and r2.detail == "1 de 2 prueba(s) falla(n)"
    assert [t.name for t in r2.tests] == ["tests/test_p.py::test_b", "tests/test_p.py::test_a"]
    assert check.tests_ran is True and check.warnings == ["tests/test_p.py::test_b usa «RN-01», que no cumple el formato RN-###"]
    # Sin reglas.json (pytest no corrió) se usan las pruebas leídas del código
    sin = with_tests(correr(root, files), None, None)
    assert sin.tests_ran is False and sin.results[1].status == "sin_verificar"


def test_build_usa_el_plugin_solo_con_sandbox_real(settings, tmp_path):
    root, files = repo(tmp_path, {"reglas_negocio.toml": REGLAS, "app/cobro.py": "x = 1\n", "tests/test_pedidos.py": TEST_PEDIDOS})
    static = pipeline.StaticResult(files=files, py=["app/cobro.py"], findings=[], complexity=[], cfg=default_config(), rules=correr(root, files))
    data = {"tests": [{"nodeid": "tests/test_p.py::test_a", "file": "tests/test_p.py", "line": 1, "rules": ["RN-002"], "outcome": "passed"}]}
    out = sandbox.SandboxOutput(phases={"venv": sandbox.PhaseResult("venv", 0), "tests": sandbox.PhaseResult("tests", 0)}, reglas=data, junit="<testsuite/>")
    cat = {"seg": 80, "test": 70, "prac": 75}
    real = pipeline.build(settings, "r1", static, out, "main", None, 1, cat)
    assert real.rules.results[1].status == "cumple" and real.rules.tests_ran
    simulado = pipeline.build(settings, "r1", static, None, "main", None, 1, cat)
    assert simulado.rules.results[1].status == "sin_verificar" and not simulado.rules.tests_ran
    sin_pytest = pipeline.build(settings, "r1", static, out, "main", None, 1, cat, analyzers=["bandit", "ruff", "coverage"])
    # Sin pytest no hay pruebas que revisar: sus reglas quedan sin verificar, con el motivo
    assert sin_pytest.rules.results[1].status == "sin_verificar" and "no se eligió pytest" in sin_pytest.rules.results[1].detail


# ─── En el análisis y en la API ───


class ClonerConPruebas(ClonerConReglas):
    """Repo con reglas_negocio.toml y una prueba marcada (sin sandbox en las pruebas: quedan sin ejecutar)."""

    contenido = REGLAS

    def clone(self, settings, repo_id, url, branch, token, attempt):
        result = super().clone(settings, repo_id, url, branch, token, attempt)
        from app.analysis import clone as clone_mod

        tmp = clone_mod.clones_root(settings) / f"{repo_id}.tmp-{attempt}"
        (tmp / "tests").mkdir(exist_ok=True)
        (tmp / "tests" / "test_pedidos.py").write_text(TEST_PEDIDOS, encoding="utf-8")
        return result


@pytest.fixture
def cloner() -> ClonerConPruebas:
    return ClonerConPruebas()


def test_analisis_con_pruebas_ligadas_y_api(client):
    job = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])
    i = job["logs"].index(next(line for line in job["logs"] if "Verificando reglas de negocio" in line))
    resumen, aviso = job["logs"][i + 1].split("\n")
    assert resumen.endswith("· 1 prueba(s) ligada(s) sin ejecutar") and "RN-099" in aviso
    body = client.get(f"/api/report/{job['report_id']}/reglas").json()
    assert body["origin"] == "repo" and body["tests_ran"] is False and len(body["warnings"]) == 1
    r2 = body["rules"][1]
    assert r2["level"] == "pruebas" and r2["status"] == "sin_verificar"
    assert r2["tests"] == [{"name": "tests/test_pedidos.py::test_cancelado_no_vuelve_a_pagado", "file": "tests/test_pedidos.py", "line": 5, "outcome": "sin_ejecutar", "message": ""}]


def repo_id(client) -> str:
    return wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])["repo_id"]


def test_cargar_reglas_desde_configuracion(client, cloner):
    cloner.contenido = None
    rid = repo_id(client)
    vacio = client.get(f"/api/projects/{rid}/reglas").json()
    assert vacio == {"active": None, "repo": None, "uploaded": None, "cloned": True, "commit": vacio["commit"]}

    malo = client.put(f"/api/projects/{rid}/reglas", json={"content": regla(id='"RN-1"')})
    assert malo.status_code == 422 and malo.json()["error"]["code"] == "invalid_rules"
    assert "línea 4" in malo.json()["error"]["message"] and "RN-###" in malo.json()["error"]["message"]

    body = client.put(f"/api/projects/{rid}/reglas", json={"content": REGLAS}).json()
    assert body["active"] == "app" and body["uploaded"]["valid"] and body["uploaded"]["project"] == "Tienda"
    assert [r["id"] for r in body["uploaded"]["rules"]] == ["RN-001", "RN-002"] and body["uploaded"]["rules"][0]["pattern"] is True

    # El siguiente análisis usa las reglas cargadas y avisa que hay que subirlas al repo
    job = wait_done(client, client.post(f"/api/repos/{rid}/analyze").json()["job_id"])
    assert any("súbelas al repositorio" in line for line in job["logs"])
    reglas_api = client.get("/api/report/latest/reglas", params={"repo": rid}).json()
    assert reglas_api["origin"] == "app" and reglas_api["source"] == reglas.APP_SOURCE and reglas_api["summary"]["total"] == 2

    assert client.delete(f"/api/projects/{rid}/reglas").json()["active"] is None


def test_el_archivo_del_repo_gana(client):
    rid = repo_id(client)
    body = client.put(f"/api/projects/{rid}/reglas", json={"content": regla()}).json()
    assert body["active"] == "repo" and body["repo"]["path"] == "reglas_negocio.toml" and body["repo"]["project"] == "Tienda"
    assert body["uploaded"]["project"] == "P"
    job = wait_done(client, client.post(f"/api/repos/{rid}/analyze").json()["job_id"])
    assert client.get(f"/api/report/{job['report_id']}/reglas").json()["origin"] == "repo"


def test_validar_y_plantilla(client):
    ok = client.post("/api/reglas/validar", json={"content": REGLAS}).json()
    assert ok["valid"] and ok["project"] == "Tienda" and len(ok["rules"]) == 2
    mal = client.post("/api/reglas/validar", json={"content": "[proyecto"}).json()
    assert mal["valid"] is False and "TOML" in mal["error"]
    res = client.get("/api/reglas/plantilla")
    assert res.status_code == 200 and "reglas_negocio.toml" in res.headers["content-disposition"]
    rs = parse(res.text)
    assert [r.id for r in rs.rules] == ["RN-001", "RN-002", "RN-003"] and rs.rules[0].forbidden == r"float\("


def test_reglas_de_otro_equipo(client, fake):
    rid = repo_id(client)
    fake.user = fake.user.__class__(id=99, login="eve", name=None, email=None, avatar_url=None)
    login(client)
    assert client.get(f"/api/projects/{rid}/reglas").status_code == 404
    assert client.put(f"/api/projects/{rid}/reglas", json={"content": REGLAS}).status_code == 404


def test_migra_bases_anteriores(tmp_path):
    path = tmp_path / "vieja.db"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE business_rule_checks (report_id TEXT PRIMARY KEY, source TEXT, project TEXT, error TEXT);
        CREATE TABLE business_rule_results (report_id TEXT NOT NULL, rule_id TEXT NOT NULL, pos INTEGER NOT NULL,
          title TEXT NOT NULL, description TEXT NOT NULL, severity TEXT NOT NULL, paths TEXT NOT NULL DEFAULT '[]',
          forbidden TEXT, required TEXT, story TEXT, owner TEXT, criterion TEXT, status TEXT NOT NULL, level TEXT NOT NULL,
          detail TEXT NOT NULL, evidence TEXT NOT NULL DEFAULT '[]', evidence_total INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (report_id, rule_id));
    """)
    old.close()
    conn = connect(str(path))
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(business_rule_checks)")}
    assert {"origin", "warnings", "tests_ran"} <= cols
    assert "tests" in {r["name"] for r in conn.execute("PRAGMA table_info(business_rule_results)")}
    conn.close()
