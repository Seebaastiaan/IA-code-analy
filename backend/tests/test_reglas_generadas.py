"""
Pruebas de reglas generadas por IA voy (app.projects.reglas_pruebas y app.projects.pruebas, PROPUESTA §6.3 y §9,
fase 4): «no cumple» vs «prueba rota», validación con ast, no implementada / fuera del código, primera corrida,
aprobación, exportación y su uso en el análisis. Con un modelo falso que responde con las pruebas escritas a mano del
repo demo, y un "sandbox" que corre pytest aquí mismo.
"""

import ast
import io
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest

from app.analyses import mapa, reglas
from app.analysis import clone as clone_mod
from app.analysis import sandbox
from app.assistant import router as assistant_router
from app.assistant.llm import Answer
from app.projects import reglas_arnes as arnes
from app.projects import reglas_pruebas as pruebas
from tests import demos
from tests.test_analysis import URL, wait_done
from tests.test_reglas_arnes import ClonerInventario, harness_of

SEED = Path(__file__).resolve().parent.parent / "seed_data"
INVENTARIO = demos.combined("inventario_demo")
PLUGINS = Path(reglas.__file__).resolve().parent.parent / "analysis"
RULES = {r.id: r for r in reglas.parse((INVENTARIO / "referencia" / "reglas_negocio.toml").read_text(encoding="utf-8")).rules}


def hand_test(rule_id: str, root: Path = INVENTARIO) -> str:
    """Las pruebas escritas a mano del demo para una regla, como un módulo propio (lo que «respondería» la IA)."""
    for path in sorted((root / "tests" / "reglas").glob("test_*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        lines = source.splitlines()
        keep = [n for n in tree.body if isinstance(n, ast.FunctionDef) and rule_id in reglas._marks(n.decorator_list)]
        if keep:
            head = [ast.get_source_segment(source, n) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
            # Las funciones auxiliares y constantes del módulo (no son pruebas) también van
            helpers = [n for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign)) or (isinstance(n, ast.FunctionDef) and not n.name.startswith("test"))]
            body = ["\n".join(lines[min([n.lineno, *(d.lineno for d in getattr(n, "decorator_list", []))]) - 1 : n.end_lineno]) for n in [*helpers, *keep]]
            return "\n".join(head) + "\n\n\n" + "\n\n\n".join(body) + "\n"
    raise KeyError(rule_id)


@pytest.fixture(scope="module")
def mp() -> mapa.ProjectMap:
    return mapa.build(INVENTARIO)


@pytest.fixture(scope="module")
def harness() -> str:
    return harness_of(INVENTARIO)


def run_local(work: Path, harness: str, files: dict[str, str]) -> dict | None:
    """Lo que hace el sandbox en modo `pruebas`, aquí: overlay y pytest con el plugin sobre tests/_ia_voy_reglas."""
    shutil.copytree(INVENTARIO, work, ignore=shutil.ignore_patterns("__pycache__", "*.db", "reglas", "referencia"))
    for rel, text in pruebas.overlay(harness, files).items():
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        (work / rel).write_text(text, encoding="utf-8")
    out = work.parent / "reglas.json"
    env = {**os.environ, "PYTHONPATH": str(PLUGINS), "IA_VOY_REGLAS_OUT": str(out), "PYTHONDONTWRITEBYTECODE": "1"}
    subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", "-p", "ia_voy_reglas", pruebas.DIR],
        cwd=work, env=env, capture_output=True, text=True, timeout=300, check=False,
    )
    return json.loads(out.read_text(encoding="utf-8")) if out.exists() else None


OK = {"venv": (0, ""), "install": (0, ""), "tests": (0, "")}


# ───────────────────────── No cumple vs. prueba rota (§9) ─────────────────────────


def test_el_plugin_separa_assert_de_lo_demas(tmp_path):
    (tmp_path / "conftest.py").write_text(
        "import pytest\n\nclass PreparacionFallida(Exception):\n    pass\n\n"
        "@pytest.fixture\ndef roto():\n    raise RuntimeError('fixture rota')\n", encoding="utf-8",
    )
    (tmp_path / "test_x.py").write_text(
        "import pytest\nfrom conftest import PreparacionFallida\n\n"
        "@pytest.mark.regla('RN-001')\ndef test_assert():\n    assert 1 == 2, 'el código no cumple'\n\n"
        "@pytest.mark.regla('RN-002')\ndef test_preparar():\n    raise PreparacionFallida('no se pudo crear el producto')\n\n"
        "@pytest.mark.regla('RN-003')\ndef test_fixture(roto):\n    pass\n\n"
        "@pytest.mark.regla('RN-004')\ndef test_raises():\n    with pytest.raises(ValueError):\n        pass\n\n"
        "@pytest.mark.regla('RN-005')\ndef test_keyerror():\n    {}['x']\n", encoding="utf-8",
    )
    out = tmp_path / "reglas.json"
    env = {**os.environ, "PYTHONPATH": str(PLUGINS), "IA_VOY_REGLAS_OUT": str(out)}
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "ia_voy_reglas"], cwd=tmp_path, env=env, capture_output=True, check=False)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["version"] == 2
    assert {t["rules"][0]: t["exception"] for t in data["tests"]} == {
        "RN-001": "AssertionError", "RN-002": "PreparacionFallida", "RN-003": "RuntimeError", "RN-004": "Failed", "RN-005": "KeyError",
    }
    # Fallar en un assert (o en pytest.raises) = el código no cumple; lo demás = la prueba está rota
    assert {t.rules[0]: t.outcome for t in reglas.plugin_tests(data)} == {
        "RN-001": "failed", "RN-002": "broken", "RN-003": "broken", "RN-004": "failed", "RN-005": "broken",
    }
    # reglas.json de la versión 1 (sin `exception`): una falla sigue contando como falla
    old = {"tests": [{"nodeid": "t", "rules": ["RN-001"], "outcome": "error"}]}
    assert reglas.plugin_tests(old)[0].outcome == "error"


def test_estados_nuevos_y_su_prioridad():
    rule = RULES["RN-002"]
    base = reglas.RuleResult(rule, "sin_verificar", "ninguno", "")

    def t(outcome):
        return reglas.LinkedTest("t", "f.py", 1, ("RN-002",), outcome)

    assert reglas.combine(base, [t("broken")], None).status == "prueba_rota"
    assert reglas.combine(base, [t("broken"), t("passed")], None).status == "prueba_rota"
    # Un assert que falla manda aunque otra prueba esté rota
    assert reglas.combine(base, [t("broken"), t("failed")], None).status == "no_cumple"
    note = reglas.AppNote("no_implementada", "No existe en el código: POST /mermas")
    assert (reglas.combine(base, [], None, note).status, reglas.combine(base, [], None, note).detail) == ("no_implementada", note.detail)
    # Si la regla tiene pruebas, la nota no cuenta
    assert reglas.combine(base, [t("passed")], None, note).status == "cumple"


def test_las_pruebas_del_repo_tienen_prioridad():
    repo = {"version": 2, "tests": [{"nodeid": "tests/test_a.py::t", "rules": ["RN-001"], "outcome": "passed"}]}
    app = {"version": 2, "tests": [
        {"nodeid": "tests/_ia_voy_reglas/test_rn001.py::t", "rules": ["RN-001"], "outcome": "failed", "exception": "AssertionError"},
        {"nodeid": "tests/_ia_voy_reglas/test_rn002.py::t", "rules": ["RN-002"], "outcome": "passed"},
    ]}
    merged = reglas.merge_app_tests(repo, app)
    assert [t["nodeid"] for t in merged["tests"]] == ["tests/test_a.py::t", "tests/_ia_voy_reglas/test_rn002.py::t"]
    assert reglas.merge_app_tests(None, app)["tests"] == app["tests"]
    assert reglas.merge_app_tests(repo, None) is repo


# ───────────────────────── Validación ─────────────────────────


def test_prueba_escrita_a_mano_es_valida(mp, harness):
    check = pruebas.validate(hand_test("RN-002"), "RN-002", mp, arnes.fixtures_of(harness))
    assert check.valid and check.errors == [] and check.tests == ["test_rn002_sku_unico"]


@pytest.mark.parametrize(
    ("code", "error"),
    [
        ("import pytest\n\ndef test_sku(como):\n    assert True\n", "no lleva @pytest.mark.regla(\"RN-002\")"),
        ("import pytest\n\n@pytest.mark.regla('RN-002', 'RN-003')\ndef test_x(como):\n    assert True\n", "dice verificar RN-003"),
        ("import pytest\n\n@pytest.mark.regla('RN-002')\ndef test_x(cliente_http):\n    assert True\n", "pide el fixture `cliente_http`"),
        ("import pytest\n\n@pytest.mark.regla('RN-002')\ndef test_x(como):\n    preparar(True, 'x')\n    assert True\n", "usa `preparar` sin definirlo"),
        ("import pytest\n\n@pytest.fixture\ndef como():\n    return None\n\n@pytest.mark.regla('RN-002')\ndef test_x(como):\n    assert True\n", "`como` ya es un fixture del arnés"),
        ("import pytest, subprocess\n\n@pytest.mark.regla('RN-002')\ndef test_x(como):\n    assert True\n", "la prueba no puede importar `subprocess`"),
        ("import pytest\n\n@pytest.mark.regla('RN-002')\ndef test_x(como):\n    assert open('x')\n", "la prueba no puede llamar a `open()`"),
        ("x = 1\n", "No hay ninguna función de prueba"),
    ],
)
def test_prueba_no_valida(mp, harness, code, error):
    check = pruebas.validate(code, "RN-002", mp, arnes.fixtures_of(harness))
    assert not check.valid and any(error in e for e in check.errors), check.errors


def test_avisos_de_la_prueba(mp, harness):
    code = "import pytest\n\n@pytest.mark.regla('RN-002')\ndef test_rn002_x(como, preparar):\n    r = como('gerente').post('/productos', json={})\n    assert r.status_code == 422\n\n\n@pytest.mark.regla('RN-002')\ndef test_rn002_y(como):\n    como('gerente')\n"
    check = pruebas.validate(code, "RN-002", mp, arnes.fixtures_of(harness))
    assert check.valid
    assert any("espera exactamente 422" in w for w in check.warnings)
    assert any("`test_rn002_y` no tiene ningún assert" in w for w in check.warnings)


def test_reparaciones_deterministas():
    # Error frecuente de los modelos pequeños, y los imports que olvidan
    code = pruebas._clean_code("```python\n@pytest.mark.regla('RN-001')\ndef_test_rn001_x(como):\n    assert Decimal('1') == 1\n```")
    assert "def test_rn001_x(como):" in code and "```" not in code
    fixed = pruebas.add_missing_imports(code)
    assert fixed.startswith("from decimal import Decimal\nimport pytest\n")
    compile(fixed, "t.py", "exec")


def test_endpoints_del_mapa(mp):
    assert pruebas.missing_endpoints(["POST /productos", "PATCH /productos/{id}", "GET /productos/7/kardex", "basura"], mp) == []
    assert pruebas.missing_endpoints(["POST /productos/{id}/devoluciones", "DELETE /ventas/{id}"], mp) == ["POST /productos/{id}/devoluciones", "DELETE /ventas/{id}"]


# ───────────────────────── Generación (modelo falso) ─────────────────────────


class FakeLLM:
    """Responde con `replies` en orden (cada respuesta es el JSON de Gemini); repite la última."""

    def __init__(self, *replies: dict) -> None:
        self.replies = list(replies)
        self.calls: list[list] = []

    def answer(self, system: str, turns: list, schema: dict, on_delta=None) -> Answer:
        self.calls.append(turns)
        return Answer(self.replies[min(len(self.calls), len(self.replies)) - 1], "Gemini 3.8 Flash")


def reply(code: str = "", tipo: str = "datos", endpoints=("POST /productos",), implementada: bool = True, motivo: str = "") -> dict:
    return {"tipo": tipo, "implementada": implementada, "motivo": motivo, "endpoints": list(endpoints), "codigo": code, "supuestos": ["Se rechaza con 409"]}


def test_generar_manda_regla_mapa_arnes_y_codigo(mp, harness):
    llm = FakeLLM(reply(hand_test("RN-002")))
    g = pruebas.generate(llm, INVENTARIO, mp, harness, RULES["RN-002"])
    assert (g.kind, g.tipo, g.assumptions, g.model) == ("prueba", "datos", ["Se rechaza con 409"], "Gemini 3.8 Flash")
    text = llm.calls[0][0].text
    assert "id: RN-002" in text and '"ruta": "/productos"' in text and "def crear_producto" in text
    # Los esquemas (con sus restricciones) y el código que más se parece a la regla
    assert "ESQUEMAS inventario/esquemas.py" in text and "class ProductoNuevo" in text
    assert "CÓDIGO inventario/rutas_productos.py" in text and "_unicos" in text
    assert len(llm.calls) == 1


def test_una_ronda_de_correccion_con_los_errores(mp, harness):
    roto = "import pytest\n\n@pytest.mark.regla('RN-002')\ndef test_rn002_x(como):\n    preparar(True, 'x')\n    assert True\n"
    llm = FakeLLM(reply(roto), reply(hand_test("RN-002")))
    g = pruebas.generate(llm, INVENTARIO, mp, harness, RULES["RN-002"])
    assert len(llm.calls) == 2 and "usa `preparar` sin definirlo" in llm.calls[1][-1].text
    assert pruebas.validate(g.code, "RN-002", mp, arnes.fixtures_of(harness)).valid


def test_una_prueba_rota_se_corrige_con_el_error_de_su_corrida(mp, harness):
    # Corrida real (inventario-demo): la prueba esperaba 201 de una venta que responde 200 y se rompió al preparar el escenario
    llm = FakeLLM(reply(hand_test("RN-002")))
    anterior = "def test_rn002_viejo(como):\n    pass\n"
    error = 'test_rn002_viejo: conftest.PreparacionFallida: la venta no se pudo realizar: 201 {"venta_id":1}'
    g = pruebas.generate(llm, INVENTARIO, mp, harness, RULES["RN-002"], broken=(anterior, error))
    turns = llm.calls[0]
    assert len(llm.calls) == 1 and [t.role for t in turns] == ["user", "model", "user"]
    assert "test_rn002_viejo" in turns[1].text and "se ROMPIÓ al preparar el escenario" in turns[2].text and "PreparacionFallida" in turns[2].text
    assert g.kind == "prueba"


def test_si_dice_no_implementada_con_endpoints_que_existen_se_le_insiste(mp, harness):
    # Corrida real con Gemini: «no implementada» con POST /citas en el mapa y el código vacío; al insistir escribió la prueba
    vacia = reply("", endpoints=["POST /productos"], implementada=False, motivo="No encontré la validación")
    llm = FakeLLM(vacia, reply(hand_test("RN-002")))
    g = pruebas.generate(llm, INVENTARIO, mp, harness, RULES["RN-002"])
    assert g.kind == "prueba" and len(llm.calls) == 2 and "SÍ existen en el mapa" in llm.calls[1][-1].text
    # Si la acción no existe en el mapa no se insiste: es «no implementada»
    falta = pruebas.generate(FakeLLM(reply("", endpoints=["POST /devoluciones"], implementada=False)), INVENTARIO, mp, harness, RULES["RN-002"])
    assert falta.kind == "no_implementada"
    # Si insiste y sigue sin código, se explica el error de siempre
    with pytest.raises(pruebas.GenerationError):
        pruebas.generate(FakeLLM(vacia), INVENTARIO, mp, harness, RULES["RN-002"])


def test_fuera_del_codigo_y_no_implementada(mp, harness):
    proceso = pruebas.generate(FakeLLM(reply(tipo="proceso", endpoints=())), INVENTARIO, mp, harness, RULES["RN-002"])
    assert (proceso.kind, proceso.code) == ("fuera_del_codigo", "")
    # La acción no existe en el mapa: no implementada, aunque la IA haya escrito código
    falta = pruebas.generate(FakeLLM(reply(hand_test("RN-002"), endpoints=["POST /devoluciones"])), INVENTARIO, mp, harness, RULES["RN-002"])
    assert (falta.kind, falta.reason) == ("no_implementada", "No existe en el código: POST /devoluciones")
    sin_endpoint = pruebas.generate(FakeLLM(reply(implementada=False, endpoints=(), motivo="No hay registro de devoluciones")), INVENTARIO, mp, harness, RULES["RN-002"])
    assert (sin_endpoint.kind, sin_endpoint.reason) == ("no_implementada", "No hay registro de devoluciones")
    # «No implementada» lo decide el mapa: si el endpoint existe, no basta con que la IA lo diga
    with pytest.raises(pruebas.GenerationError):
        pruebas.generate(FakeLLM(reply(implementada=False, motivo="no valida el precio")), INVENTARIO, mp, harness, RULES["RN-002"])


# ───────────────────────── Primera corrida (las pruebas del demo) ─────────────────────────


def test_primera_corrida_da_el_veredicto_esperado(tmp_path, harness):
    pytest.importorskip("sqlalchemy")
    ids = ["RN-002", "RN-006", "RN-017"]
    files = {pruebas.test_path(RULES[i]): hand_test(i) for i in ids}
    data = run_local(tmp_path / "repo", harness, files)
    results = pruebas.read_run(data, OK, [RULES[i] for i in ids])
    # RN-006 y RN-017 están rotas a propósito en el demo (referencia/ESPERADO.md)
    assert {i: r.verdict for i, r in results.items()} == {"RN-002": "cumple", "RN-006": "no_cumple", "RN-017": "no_cumple"}
    assert any(t.outcome == "failed" for t in results["RN-017"].tests)


def test_prueba_que_no_puede_preparar_queda_rota(tmp_path, harness):
    pytest.importorskip("sqlalchemy")
    code = hand_test("RN-002").replace('crear_producto(sku="CAF-001")', 'crear_producto(sku="CAF-001", unidad_base="pza")', 1)
    assert code != hand_test("RN-002")
    results = pruebas.read_run(run_local(tmp_path / "repo", harness, {pruebas.test_path(RULES["RN-002"]): code}), OK, [RULES["RN-002"]])
    assert results["RN-002"].verdict == "prueba_rota" and "no se pudo crear el producto" in results["RN-002"].tests[0].message


def test_corrida_que_no_llega_a_pytest():
    results = pruebas.read_run(None, {"venv": (0, ""), "install": (1, "ERROR: No matching distribution found for x"), "tests": (None, "")}, [RULES["RN-002"]])
    assert results["RN-002"].verdict == "prueba_rota" and "No se pudieron instalar" in results["RN-002"].detail


# ───────────────────────── Endpoints ─────────────────────────


@pytest.fixture
def cloner() -> ClonerInventario:
    return ClonerInventario()


class LocalRunner:
    """Sustituye a WSL/Docker en modo `pruebas`: pytest con el plugin sobre una copia del clon."""

    def __init__(self, settings, repo_id: str, mode: str, overlay: dict[str, str]):
        self.work = clone_mod.clones_root(settings) / f"{repo_id}.{mode}-local"
        shutil.rmtree(self.work, ignore_errors=True)
        shutil.copytree(clone_mod.clone_dir(settings, repo_id), self.work / "repo")
        for rel, text in overlay.items():
            (self.work / "repo" / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.work / "repo" / rel).write_text(text, encoding="utf-8")
        target = arnes.SMOKE if mode == "arnes" else pruebas.DIR
        env = {**os.environ, "PYTHONPATH": str(PLUGINS), "IA_VOY_REGLAS_OUT": str(self.work / "reglas.json")}
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", "-p", "ia_voy_reglas", f"--junitxml={self.work / 'junit.xml'}", "-o", "junit_family=xunit1", target],
            cwd=self.work / "repo", env=env, capture_output=True, text=True, timeout=300, check=False,
        )
        self.code, self.log = proc.returncode, proc.stdout + proc.stderr

    async def wait(self, name: str) -> sandbox.PhaseResult:
        return sandbox.PhaseResult(name, self.code if name == "tests" else 0, self.log if name == "tests" else "")

    def output(self) -> sandbox.SandboxOutput:
        def read(name):
            p = self.work / name
            return p.read_text(encoding="utf-8") if p.exists() else None

        data = read("reglas.json")
        return sandbox.SandboxOutput(junit=read("junit.xml"), reglas=json.loads(data) if data else None)

    def close(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)


@pytest.fixture
def local_sandbox(settings, monkeypatch):
    settings.sandbox = "wsl"
    modes: list[str] = []

    def start(settings_, repo_id, mode="analisis", overlay=None):
        modes.append(mode)
        if mode == "analisis":
            # El análisis de estas pruebas corre sin sandbox (se simula); aquí importan la prueba de humo y la corrida
            return None, "sin sandbox en las pruebas"
        return LocalRunner(settings_, repo_id, mode, overlay or {}), None

    monkeypatch.setattr(sandbox, "start", start)
    monkeypatch.setattr(sandbox, "_available", lambda s: None)
    return modes


def wait_free(client, rid: str) -> dict:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        view = client.get(f"/api/projects/{rid}/reglas/pruebas").json()
        if view["busy"] is None:
            return view
        time.sleep(0.2)
    raise AssertionError("no terminó")


def ready_project(client) -> str:
    """Proyecto con el inventario, sus reglas cargadas en la app y el arnés del repo aprobado."""
    rid = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])["repo_id"]
    assert client.put(f"/api/projects/{rid}/reglas", json={"content": (INVENTARIO / "referencia/reglas_negocio.toml").read_text(encoding="utf-8")}).status_code == 200
    client.post(f"/api/projects/{rid}/reglas/arnes/repo")
    client.post(f"/api/projects/{rid}/reglas/arnes/humo")
    deadline = time.monotonic() + 120
    while client.get(f"/api/projects/{rid}/reglas/arnes").json()["harness"]["smoke"] == "corriendo" and time.monotonic() < deadline:
        time.sleep(0.2)
    assert client.post(f"/api/projects/{rid}/reglas/arnes/aprobar").json()["ready"]
    return rid


def by_rule(view: dict) -> dict[str, dict]:
    return {r["id"]: r for r in view["rules"]}


class RuleLLM:
    """Gemini falso que contesta según la regla del prompt: las pruebas escritas a mano o un caso especial."""

    def __init__(self, special: dict[str, dict] | None = None) -> None:
        self.special = special or {}
        self.asked: list[str] = []

    def answer(self, system: str, turns: list, schema: dict, on_delta=None) -> Answer:
        rid = turns[0].text.split("id: ", 1)[1].split("\n", 1)[0]
        self.asked.append(rid)
        return Answer(self.special.get(rid) or reply(hand_test(rid)), "Gemini 3.8 Flash")


def test_generar_correr_aprobar_exportar_y_analizar(client, settings, local_sandbox):
    pytest.importorskip("sqlalchemy")
    settings.gemini_api_key = "clave"
    llm = RuleLLM({"RN-019": reply(tipo="proceso", endpoints=())}) if "RN-019" in RULES else RuleLLM()
    client.app.dependency_overrides[assistant_router.get_llm] = lambda: llm
    rid = ready_project(client)

    view = client.get(f"/api/projects/{rid}/reglas/pruebas").json()
    assert view["harness_ready"] and view["can_generate"] and len(view["rules"]) == 18
    assert {r["state"] for r in view["rules"]} == {"sin_prueba"}
    # El clon del demo trae sus pruebas escritas a mano: el repo ya verifica las reglas (tienen prioridad)
    assert by_rule(view)["RN-002"]["repo_tests"] >= 1

    ids = ["RN-002", "RN-006", "RN-017"]
    assert client.post(f"/api/projects/{rid}/reglas/pruebas", json={"ids": ids}).json()["busy"]["kind"] == "generando"
    view = wait_free(client, rid)
    assert sorted(llm.asked) == ids and view["messages"] == []
    rows = by_rule(view)
    assert rows["RN-002"]["state"] == "borrador" and rows["RN-002"]["test"]["file"] == pruebas.test_path(RULES["RN-002"])
    assert rows["RN-002"]["test"]["blocked"] == "Córrela primero en el sandbox"
    # Sin correrla no se aprueba
    view = client.post(f"/api/projects/{rid}/reglas/pruebas/aprobar", json={"ids": ["RN-002"]}).json()
    assert view["messages"] == ["RN-002: Córrela primero en el sandbox"]

    assert client.post(f"/api/projects/{rid}/reglas/pruebas/correr", json={}).json()["busy"]["kind"] == "corriendo"
    view = wait_free(client, rid)
    rows = by_rule(view)
    assert {i: rows[i]["test"]["run"]["verdict"] for i in ids} == {"RN-002": "cumple", "RN-006": "no_cumple", "RN-017": "no_cumple"}
    assert "pruebas" in local_sandbox

    view = client.post(f"/api/projects/{rid}/reglas/pruebas/aprobar", json={"ids": ids}).json()
    assert {by_rule(view)[i]["state"] for i in ids} == {"aprobada"} and view["messages"] == []
    assert by_rule(view)["RN-002"]["test"]["approved_by"]

    # Editar invalida la corrida y la aprobación
    edited = by_rule(view)["RN-002"]["test"]["code"] + "\n# revisada\n"
    row = by_rule(client.put(f"/api/projects/{rid}/reglas/pruebas/RN-002", json={"code": edited}).json())["RN-002"]
    assert (row["state"], row["test"]["origin"], row["test"]["run_status"]) == ("borrador", "manual", "pendiente")

    # Exportar: reglas + arnés + aprobadas, en tests/reglas/
    res = client.get(f"/api/projects/{rid}/reglas/exportar")
    assert res.status_code == 200 and res.headers["content-type"] == "application/zip"
    names = set(zipfile.ZipFile(io.BytesIO(res.content)).namelist())
    approved = {"tests/reglas/" + Path(pruebas.test_path(RULES[i])).name for i in ("RN-006", "RN-017")}
    assert names == {"reglas_negocio.toml", "tests/reglas/conftest.py", *approved}

    # El análisis manda las aprobadas al sandbox (y no las editadas sin aprobar)
    from app.analysis import pipeline
    from app.db import session

    with session(settings.database_path) as conn:
        overlay, notes, declared = pipeline.app_rule_tests(conn, settings, rid)
    assert set(overlay) == {pruebas.CONFTEST, by_rule(view)["RN-006"]["test"]["file"], by_rule(view)["RN-017"]["test"]["file"]}
    assert notes == {} and {t.rules for t in declared} == {("RN-006",), ("RN-017",)}

    # El código cambia y ya no tiene una ruta que usa la prueba aprobada de RN-006: fallaría por eso, no porque el código
    # viole la regla. No se corre, queda como prueba rota con el motivo y la vista lo dice para escribirla de nuevo
    with session(settings.database_path) as conn:
        conn.execute("UPDATE business_rule_tests SET endpoints = ? WHERE repo_id = ? AND rule_id = 'RN-006'", (json.dumps(["DELETE /ya-no-existe/{id}"]), rid))
    with session(settings.database_path) as conn:
        overlay, notes, declared = pipeline.app_rule_tests(conn, settings, rid)
    assert by_rule(view)["RN-006"]["test"]["file"] not in overlay and {t.rules for t in declared} == {("RN-017",)}
    assert notes["RN-006"].status == "prueba_rota" and "DELETE /ya-no-existe/{id}, que ya no está en el código" in notes["RN-006"].detail
    gone = by_rule(client.get(f"/api/projects/{rid}/reglas/pruebas").json())["RN-006"]["test"]["gone_endpoints"]
    assert gone == ["DELETE /ya-no-existe/{id}"]


def test_generar_necesita_el_arnes_aprobado(client, settings):
    settings.gemini_api_key = "clave"
    client.app.dependency_overrides[assistant_router.get_llm] = lambda: RuleLLM()
    rid = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])["repo_id"]
    client.put(f"/api/projects/{rid}/reglas", json={"content": (INVENTARIO / "referencia/reglas_negocio.toml").read_text(encoding="utf-8")})
    view = client.get(f"/api/projects/{rid}/reglas/pruebas").json()
    assert not view["harness_ready"] and not view["can_generate"] and len(view["rules"]) == 18
    res = client.post(f"/api/projects/{rid}/reglas/pruebas", json={})
    assert res.status_code == 409 and res.json()["error"]["code"] == "harness_not_ready"


def test_no_implementada_cuenta_en_el_analisis_sin_correr(client, settings, local_sandbox):
    pytest.importorskip("sqlalchemy")
    settings.gemini_api_key = "clave"
    llm = RuleLLM({"RN-012": reply(endpoints=["POST /mermas/{id}/revision"])})
    client.app.dependency_overrides[assistant_router.get_llm] = lambda: llm
    rid = ready_project(client)
    client.post(f"/api/projects/{rid}/reglas/pruebas", json={"ids": ["RN-012"]})
    row = by_rule(wait_free(client, rid))["RN-012"]
    assert (row["test"]["kind"], row["test"]["blocked"]) == ("no_implementada", None)
    client.post(f"/api/projects/{rid}/reglas/pruebas/aprobar", json={"ids": ["RN-012"]})

    from app.analysis import pipeline
    from app.db import session

    with session(settings.database_path) as conn:
        overlay, notes, _ = pipeline.app_rule_tests(conn, settings, rid)
    assert overlay is None and notes["RN-012"].status == "no_implementada"
    # El repo del demo ya prueba RN-012 (tests/reglas): esas pruebas mandan y la nota no se usa
    check = reglas.run(INVENTARIO, [p.relative_to(INVENTARIO).as_posix() for p in INVENTARIO.rglob("*.py")], lambda f: (INVENTARIO / f).read_text(encoding="utf-8").splitlines(),
                       (INVENTARIO / "referencia/reglas_negocio.toml").read_text(encoding="utf-8"))
    sin_pruebas = reglas.with_app(reglas.RulesCheck(source="x", project="x", patterns=check.patterns, declared=[]), [], notes)
    assert {r.rule.id: r.status for r in sin_pruebas.results}["RN-012"] == "no_implementada"


def test_una_prueba_sin_aprobar_dice_lo_que_se_sabe_en_el_reporte():
    code = "def test_rn001_x():\n    pass\n"
    h = arnes.code_hash(code)
    row = lambda verdict, strength=None, **kw: {
        "kind": "prueba", "code": code, "run_hash": h, "run_result": json.dumps({"verdict": verdict}),
        "strength_hash": h if strength else None, "strength_result": json.dumps({"status": strength}) if strength else None, **kw,
    }
    assert pruebas.unapproved_note(row("cumple", "parcial")) == (
        "Su prueba pasa (no notó todas las violaciones que se le inyectaron), pero todavía no cuenta: revísala y apruébala en Configuración → Reglas"
    )
    assert pruebas.unapproved_note(row("no_cumple")).startswith("Su prueba falla, pero todavía no cuenta")
    # Sin correr con su código actual no se sabe nada
    assert pruebas.unapproved_note(row("cumple", run_hash="otro")) is None
    assert pruebas.unapproved_note(row("cumple", kind="no_implementada")) is None
