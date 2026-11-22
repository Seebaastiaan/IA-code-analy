"""
Arnés de las pruebas de reglas de negocio (app.projects.reglas_arnes y sus endpoints, PROPUESTA_REGLAS_VERIFICABLES.md
§7, fase 3): validación con `ast`, prueba de humo y el ciclo proponer → probar → aprobar, con un modelo falso y un
"sandbox" que corre pytest aquí mismo sobre una copia del repo demo.
"""

import ast
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.analyses import mapa
from app.analysis import clone as clone_mod
from app.analysis import sandbox
from app.assistant import router as assistant_router
from app.assistant.llm import Answer
from app.projects import reglas_arnes as arnes
from tests import demos
from tests.conftest import FakeCloner
from tests.test_analysis import URL, wait_done

SEED = Path(__file__).resolve().parent.parent / "seed_data"
INVENTARIO = demos.combined("inventario_demo")
RESERVAS = demos.combined("reservas_demo")


def harness_of(root: Path) -> str:
    """El arnés como lo armaría IA voy si la IA respondiera con el conftest.py escrito a mano del demo."""
    return arnes.assemble(arnes.demo_body((root / "tests" / "reglas" / "conftest.py").read_text(encoding="utf-8")))


def run_smoke(root: Path, code: str, work: Path) -> arnes.SmokeResult:
    """Lo mismo que hace el sandbox en modo `arnes`, pero aquí: copia, overlay y pytest sobre la prueba de humo."""
    mp = mapa.build(root)
    shutil.copytree(root, work, ignore=shutil.ignore_patterns("__pycache__", "*.db"))
    for rel, text in arnes.overlay(code, mp).items():
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        (work / rel).write_text(text, encoding="utf-8")
    junit = work.parent / "junit.xml"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", f"--junitxml={junit}", "-o", "junit_family=xunit1", arnes.SMOKE],
        cwd=work, capture_output=True, text=True, timeout=300, check=False,
    )
    xml = junit.read_text(encoding="utf-8") if junit.exists() else None
    return arnes.read_smoke(xml, {"venv": (0, ""), "install": (0, ""), "tests": (proc.returncode, proc.stdout + proc.stderr)})


# ───────────────────────── Validación ─────────────────────────


MINIMO = '''
import pytest
from inventario.main import app


def preparar(condicion, motivo):
    if not condicion:
        raise RuntimeError(motivo)


@pytest.fixture
def api():
    return app


@pytest.fixture
def como():
    return lambda rol: app


@pytest.fixture
def crear_producto():
    return lambda: {"id": 1}
'''


@pytest.fixture(scope="module")
def inventario_map() -> mapa.ProjectMap:
    return mapa.build(INVENTARIO)


def test_arnes_minimo_valido(inventario_map):
    check = arnes.validate(MINIMO, inventario_map)
    assert check.valid and check.errors == []
    assert check.fixtures == ["api", "como", "crear_producto"]
    # El inventario usa datetime.now (fechas de los movimientos): conviene un reloj
    assert any("reloj" in w for w in check.warnings)


@pytest.mark.parametrize(
    ("change", "error"),
    [
        (lambda c: c.replace("def api", "def cliente"), "Falta el fixture `api`"),
        (lambda c: c.replace("def preparar", "def otro"), "Falta la función `preparar(condicion, motivo)`"),
        (lambda c: "import subprocess\n" + c, "el arnés no puede importar `subprocess`"),
        (lambda c: "from shutil import rmtree\n" + c, "el arnés no puede importar `shutil`"),
        (lambda c: "from urllib.request import urlopen\n" + c, "el arnés no puede importar `urllib.request`"),
        (lambda c: c + "\nX = open('/etc/passwd').read()\n", "el arnés no puede llamar a `open()`"),
        (lambda c: c + "\nimport os\nos.system('rm -rf /')\n", "el arnés no puede llamar a `os.system()`"),
        (lambda c: "import requests_mock\n" + c, "`requests_mock` no es de la biblioteca estándar, del framework ni del proyecto"),
        (lambda c: "from .db import Base\n" + c, "usa imports absolutos"),
        (lambda c: c + "\ndef roto(:\n", "error de sintaxis"),
    ],
)
def test_arnes_no_valido(inventario_map, change, error):
    check = arnes.validate(change(MINIMO), inventario_map)
    assert not check.valid
    assert any(error in e for e in check.errors), check.errors


def test_lo_que_la_ia_suele_inventar():
    """Errores reales de arneses propuestos por Gemini para reservas_demo: se detectan sin ejecutar nada."""
    mp = mapa.build(RESERVAS)
    code = MINIMO.replace("from inventario.main import app", "from reservas import db, reloj\nfrom reservas.app import crear_app\napp = crear_app()") + '''

@pytest.fixture
def reloj(monkeypatch):
    monkeypatch.setattr(reloj, "ahora", lambda: None)


def buscar(sesion):
    return sesion.scalar(db.select(1))
'''
    errors = arnes.validate(code, mp).errors
    # El fixture `reloj` tapa el módulo reservas.reloj (monkeypatch.setattr(reloj, …) parcharía el fixture)
    assert any(e.startswith("línea ") and "`reloj` tapa lo importado en la línea 3" in e for e in errors), errors
    # reservas/db.py no define `select` (viene de sqlalchemy)
    assert any("`reservas.db` no tiene `select`" in e for e in errors), errors
    base = MINIMO.replace("from inventario.main import app", "from reservas.app import crear_app\napp = crear_app()")
    assert not arnes.validate("from reservas.citas import no_existe\n" + base, mp).valid
    # Lo que sí existe pasa: módulos, funciones y submódulos
    assert arnes.validate("from reservas import db as base, citas\nfrom reservas.citas import dinero\n" + base + "\nX = base.sesion\n", mp).valid


def test_avisa_si_usa_la_base_real(inventario_map):
    code = MINIMO + "\n\ndef usuario():\n    from inventario.db import SessionLocal\n    return SessionLocal()\n"
    check = arnes.validate(code, inventario_map)
    assert check.valid
    assert any("usa la base real del proyecto (`inventario.db.SessionLocal`)" in w for w in check.warnings)


def test_dependencias_del_repo_se_pueden_importar(inventario_map):
    code = "import jwt_extra\n" + MINIMO
    assert not arnes.validate(code, inventario_map).valid
    allowed = arnes.declared_imports("fastapi==0.1\njwt-extra>=2  # comentario\n-r otro.txt\nPyJWT\n")
    assert {"fastapi", "jwt_extra", "jwt"} <= allowed
    assert arnes.validate(code, inventario_map, allowed).valid


def test_avisa_si_faltan_reloj_y_buzon():
    code = MINIMO.replace("from inventario.main import app", "from reservas.app import crear_app\napp = crear_app()")
    check = arnes.validate(code, mapa.build(RESERVAS))
    assert check.valid
    assert sum("reloj" in w or "buzon" in w for w in check.warnings) == 2


# ───────────────────────── Armado ─────────────────────────


def test_armado_quita_lo_que_ya_trae_ia_voy():
    body = '''"""Docstring de la IA."""

from datetime import datetime

import pytest


class PreparacionFallida(Exception):
    pass


def preparar(condicion, motivo):
    assert condicion, motivo


@pytest.fixture
def api():
    return datetime.now()
'''
    code = arnes.assemble(body)
    assert code.startswith('"""\nArnés de las pruebas de reglas de negocio, propuesto por IA voy')
    assert "Docstring de la IA" not in code
    # Una sola PreparacionFallida y un solo preparar: los de IA voy (no `assert`, que contaría como «no cumple»)
    assert code.count("class PreparacionFallida") == 1 and code.count("def preparar") == 1
    assert "raise PreparacionFallida(motivo)" in code and "assert condicion" not in code
    # Los imports de la IA quedan antes de la base
    assert code.index("import pytest") < code.index("class PreparacionFallida") < code.index("def api")
    compile(code, "conftest.py", "exec")


def test_prueba_de_humo_usa_roles_y_lista_del_mapa(inventario_map):
    smoke = arnes.smoke_test(inventario_map, ["api", "como", "crear_producto", "vender"])
    assert "ROLES = ['cajero', 'barista', 'gerente', 'almacenista']" in smoke
    # Un GET sin parámetros que pide usuario (prueba que como(rol) autentica)
    assert "LISTA = '/alertas'" in smoke
    assert "CREAR = ['crear_producto']" in smoke and "EXTRAS = []" in smoke
    compile(smoke, "test_humo_arnes.py", "exec")
    reservas = arnes.smoke_test(mapa.build(RESERVAS), ["api", "como", "reloj", "buzon"])
    assert "LISTA = '/citas'" in reservas and "EXTRAS = ['reloj', 'buzon']" in reservas


JUNIT = """<testsuites><testsuite>
<testcase classname="t" name="test_humo_api"/>
<testcase classname="t" name="test_humo_como[cajero]"><failure message="AssertionError: como('cajero'): GET /alertas respondió 401, el usuario no quedó autenticado">x</failure></testcase>
<testcase classname="t" name="test_humo_como[gerente]"><failure message="AssertionError: otra">x</failure></testcase>
<testcase classname="t" name="test_humo_crear[crear_producto]"><error message="PreparacionFallida: no se pudo crear el producto: 422">x</error></testcase>
<testcase classname="t" name="test_humo_extras[None]"><skipped message="sin extras"/></testcase>
</testsuite></testsuites>"""
OK = {"venv": (0, ""), "install": (0, "")}


def test_resultado_de_la_prueba_de_humo():
    result = arnes.read_smoke(JUNIT, {**OK, "tests": (1, "")})
    assert result.status == "fallo"
    # Un solo aviso: la primera falla, con el fixture que la causó
    assert result.message == "como('cajero'): AssertionError: como('cajero'): GET /alertas respondió 401, el usuario no quedó autenticado (y 2 más)"
    assert [t.outcome for t in result.tests] == ["passed", "failed", "failed", "error", "skipped"]
    crear = '<testsuite><testcase name="test_humo_api"/><testcase name="test_humo_crear[crear_producto]"><error message="PreparacionFallida: no se pudo crear el producto: 422">x</error></testcase></testsuite>'
    error = arnes.read_smoke(crear, {**OK, "tests": (1, "")})
    assert error.message == "crear_producto: PreparacionFallida: no se pudo crear el producto: 422"
    passed = arnes.read_smoke('<testsuite><testcase name="test_humo_api"/><testcase name="test_humo_como[a]"/></testsuite>', {**OK, "tests": (0, "")})
    assert (passed.status, passed.message) == ("paso", "2 comprobaciones pasaron")


def test_prueba_de_humo_que_no_llega_a_correr():
    install = arnes.read_smoke(None, {"venv": (0, ""), "install": (1, "Collecting x\nERROR: No matching distribution found for fastapi==99"), "tests": (None, "")})
    assert install.message == "No se pudieron instalar las dependencias del proyecto: ERROR: No matching distribution found for fastapi==99"
    conftest = arnes.read_smoke(None, {**OK, "tests": (4, "ImportError while loading conftest '/w/tests/_ia_voy_reglas/conftest.py'.\nE   ModuleNotFoundError: No module named 'inventario.base'")})
    assert conftest.status == "fallo" and "No module named 'inventario.base'" in conftest.message
    timeout = arnes.read_smoke(None, {**OK, "tests": (None, "")})
    assert "no terminó" in timeout.message


# ───────────────────────── Con los repos demo ─────────────────────────


@pytest.mark.parametrize(("root", "needs", "checks"), [(INVENTARIO, ("sqlalchemy",), 6), (RESERVAS, ("sqlalchemy", "flask"), 8)], ids=["inventario", "reservas"])
def test_arnes_del_demo_pasa_la_prueba_de_humo(tmp_path, root, needs, checks):
    for package in needs:
        pytest.importorskip(package)
    code = harness_of(root)
    assert arnes.validate(code, mapa.build(root), arnes.declared_imports(arnes.requirements_text(root))).valid
    result = run_smoke(root, code, tmp_path / "repo")
    assert (result.status, result.message) == ("paso", f"{checks} comprobaciones pasaron"), result.tests


def test_arnes_que_no_autentica_falla_con_un_solo_aviso(tmp_path):
    pytest.importorskip("sqlalchemy")
    code = harness_of(INVENTARIO).replace('headers={"Authorization": f"Bearer prueba-{rol}"}', 'headers={"Authorization": f"Bearer otro-{rol}"}')
    result = run_smoke(INVENTARIO, code, tmp_path / "repo")
    assert result.status == "fallo"
    assert result.message.startswith("como('cajero'): AssertionError: como('cajero'): GET /alertas respondió 401, el usuario no quedó autenticado")
    # crear_producto también falla (crea como gerente), pero el aviso es uno
    assert sum(t.outcome != "passed" for t in result.tests) >= 5


def test_repo_que_ya_trae_su_arnes(inventario_map):
    path, code = arnes.repo_harness(INVENTARIO, inventario_map)
    assert path == "tests/reglas/conftest.py" and "def como" in code


# ───────────────────────── Con Gemini (falso) ─────────────────────────


class FakeLLM:
    def __init__(self, reply: dict) -> None:
        self.reply = reply
        self.calls: list[dict] = []

    def answer(self, system: str, turns: list, schema: dict, on_delta=None) -> Answer:
        self.calls.append({"system": system, "turns": turns, "schema": schema})
        return Answer(self.reply, "Gemini 3.8 Flash")


def test_generar_manda_el_mapa_y_los_archivos(inventario_map):
    llm = FakeLLM({"codigo": "```python\n" + MINIMO + "\n```", "supuestos": ["El token es `Bearer <token>` del usuario", "  "]})
    proposed = arnes.generate(llm, INVENTARIO, inventario_map)
    text = llm.calls[0]["turns"][0].text
    assert '"ruta": "/productos"' in text and '"roles": ["gerente", "almacenista"]' in text
    # Los archivos que señala el mapa (la app, la base, el usuario actual) y el conftest.py del repo
    for f in ("inventario/main.py", "inventario/db.py", "inventario/auth.py", "tests/reglas/conftest.py"):
        assert f"ARCHIVO {f}" in text
    assert "def usuario_actual" in text
    assert "`como`" in llm.calls[0]["system"] and "NO los escribas" in llm.calls[0]["system"]
    assert proposed.assumptions == ["El token es `Bearer <token>` del usuario"]
    assert proposed.code.count("def preparar") == 1 and "```" not in proposed.code
    assert proposed.model == "Gemini 3.8 Flash"


def test_generar_sin_framework_o_sin_respuesta(tmp_path, inventario_map):
    with pytest.raises(arnes.HarnessError, match="No se reconoció"):
        arnes.generate(FakeLLM({}), tmp_path, mapa.build(tmp_path))
    with pytest.raises(arnes.HarnessError) as exc:
        arnes.generate(FakeLLM({"codigo": "  ", "supuestos": []}), INVENTARIO, inventario_map)
    assert exc.value.code == "empty_harness"


class SequenceLLM(FakeLLM):
    """Responde con una respuesta distinta en cada llamada."""

    def __init__(self, *replies: dict) -> None:
        super().__init__({})
        self.replies = list(replies)

    def answer(self, system: str, turns: list, schema: dict, on_delta=None) -> Answer:
        self.calls.append({"system": system, "turns": turns, "schema": schema})
        return Answer(self.replies.pop(0), "Gemini 3.8 Flash")


def test_generar_corrige_una_vez_si_el_arnes_no_es_valido(inventario_map):
    roto = {"codigo": "def api(:\n    pass", "supuestos": []}
    bueno = {"codigo": MINIMO, "supuestos": ["corregido"]}
    llm = SequenceLLM(roto, bueno)
    proposed = arnes.generate(llm, INVENTARIO, inventario_map)
    assert len(llm.calls) == 2 and proposed.assumptions == ["corregido"]
    # La segunda llamada trae lo que contestó la IA y los errores de la validación
    again = llm.calls[1]["turns"]
    assert [t.role for t in again] == ["user", "model", "user"] and "error de sintaxis" in again[2].text
    # Un arnés válido no gasta la segunda llamada
    ok = SequenceLLM(bueno)
    arnes.generate(ok, INVENTARIO, inventario_map)
    assert len(ok.calls) == 1


# ───────────────────────── Endpoints ─────────────────────────


class ClonerInventario(FakeCloner):
    """El clon es el repo demo del inventario."""

    def clone(self, settings, repo_id, url, branch, token, attempt):
        result = super().clone(settings, repo_id, url, branch, token, attempt)
        tmp = clone_mod.clones_root(settings) / f"{repo_id}.tmp-{attempt}"
        shutil.copytree(INVENTARIO, tmp, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.db"))
        return result


@pytest.fixture
def cloner() -> ClonerInventario:
    return ClonerInventario()


class LocalRunner:
    """Sustituye a WSL/Docker: corre la prueba de humo con el Python de las pruebas sobre una copia del clon."""

    def __init__(self, settings, repo_id: str, overlay: dict[str, str]):
        work = clone_mod.clones_root(settings) / f"{repo_id}.arnes-local"
        shutil.rmtree(work, ignore_errors=True)
        shutil.copytree(clone_mod.clone_dir(settings, repo_id), work / "repo")
        for rel, text in overlay.items():
            (work / "repo" / rel).parent.mkdir(parents=True, exist_ok=True)
            (work / "repo" / rel).write_text(text, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", f"--junitxml={work / 'junit.xml'}", "-o", "junit_family=xunit1", arnes.SMOKE],
            cwd=work / "repo", capture_output=True, text=True, timeout=300, check=False,
        )
        self.work = work
        self.code = proc.returncode
        self.log = proc.stdout + proc.stderr

    async def wait(self, name: str) -> sandbox.PhaseResult:
        return sandbox.PhaseResult(name, self.code if name == "tests" else 0, self.log if name == "tests" else "")

    def output(self) -> sandbox.SandboxOutput:
        junit = self.work / "junit.xml"
        return sandbox.SandboxOutput(junit=junit.read_text(encoding="utf-8") if junit.exists() else None)

    def close(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)


@pytest.fixture
def local_sandbox(settings, monkeypatch):
    settings.sandbox = "wsl"
    started: list[str] = []

    def start(settings_, repo_id, mode="analisis", overlay=None):
        assert mode == "arnes"
        started.append(repo_id)
        return LocalRunner(settings_, repo_id, overlay or {}), None

    monkeypatch.setattr(sandbox, "start", start)
    monkeypatch.setattr(sandbox, "_available", lambda s: None)
    return started


def project(client) -> str:
    # El análisis corre sin sandbox (lo que se cambia es solo la prueba de humo del arnés)
    return wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])["repo_id"]


def wait_smoke(client, rid: str) -> dict:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        view = client.get(f"/api/projects/{rid}/reglas/arnes").json()
        if view["harness"]["smoke"] != "corriendo":
            return view
        time.sleep(0.2)
    raise AssertionError("la prueba de humo no terminó")


def test_mapa_y_arnes_de_un_proyecto(client):
    rid = project(client)
    mp = client.get(f"/api/projects/{rid}/reglas/mapa").json()
    assert mp["framework"] == "fastapi" and len(mp["endpoints"]) == 18 and "commit" in mp
    view = client.get(f"/api/projects/{rid}/reglas/arnes").json()
    assert view["cloned"] and view["harness"] is None and not view["ready"]
    assert view["map"]["framework"] == "fastapi" and view["map"]["endpoints"] == 18 and view["map"]["models"] == 9
    assert view["map"]["roles"] == ["cajero", "barista", "gerente", "almacenista"]
    assert view["repo_harness"] == "tests/reglas/conftest.py"
    # Sin GEMINI_API_KEY ni sandbox (SANDBOX=off por defecto)
    assert view["can_generate"] is False and view["sandbox"] is False
    assert client.post(f"/api/projects/{rid}/reglas/arnes").json()["error"]["code"] == "llm_not_configured"
    assert client.get("/api/projects/no-existe/reglas/arnes").status_code == 404


def test_proponer_probar_y_aprobar(client, settings, local_sandbox):
    pytest.importorskip("sqlalchemy")
    settings.gemini_api_key = "clave"
    llm = FakeLLM({"codigo": arnes.demo_body((INVENTARIO / "tests/reglas/conftest.py").read_text(encoding="utf-8")), "supuestos": ["Los tokens se guardan en Usuario.token"]})
    client.app.dependency_overrides[assistant_router.get_llm] = lambda: llm
    rid = project(client)

    view = client.post(f"/api/projects/{rid}/reglas/arnes").json()
    h = view["harness"]
    assert (h["origin"], h["model"], h["assumptions"], h["smoke"], h["errors"]) == ("ia", "Gemini 3.8 Flash", ["Los tokens se guardan en Usuario.token"], "pendiente", [])
    assert {"api", "como", "crear_producto"} <= set(h["fixtures"])
    # No se aprueba sin prueba de humo
    assert client.post(f"/api/projects/{rid}/reglas/arnes/aprobar").json()["error"]["code"] == "smoke_required"

    assert client.post(f"/api/projects/{rid}/reglas/arnes/humo").json()["harness"]["smoke"] in ("corriendo", "paso")
    view = wait_smoke(client, rid)
    assert (view["harness"]["smoke"], view["harness"]["smoke_message"]) == ("paso", "6 comprobaciones pasaron"), view["harness"]["smoke_tests"]
    assert local_sandbox == [rid]

    view = client.post(f"/api/projects/{rid}/reglas/arnes/aprobar").json()
    assert view["ready"] and view["harness"]["approved"] and view["harness"]["approved_by"]

    # Editarlo invalida la prueba de humo y la aprobación
    broken = view["harness"]["code"].replace("Bearer prueba-{rol}\"}", "Bearer otro-{rol}\"}")
    view = client.put(f"/api/projects/{rid}/reglas/arnes", json={"code": broken}).json()
    assert (view["harness"]["origin"], view["harness"]["smoke"], view["ready"]) == ("manual", "pendiente", False)
    client.post(f"/api/projects/{rid}/reglas/arnes/humo")
    view = wait_smoke(client, rid)
    assert view["harness"]["smoke"] == "fallo"
    assert view["harness"]["smoke_message"].startswith("como('cajero'): AssertionError: como('cajero'): GET /alertas respondió 401")

    # Con errores de validación no se corre
    client.put(f"/api/projects/{rid}/reglas/arnes", json={"code": "import subprocess\n"})
    res = client.post(f"/api/projects/{rid}/reglas/arnes/humo")
    assert res.status_code == 422 and res.json()["error"]["code"] == "invalid_harness"


def test_usar_el_arnes_del_repo(client):
    rid = project(client)
    view = client.post(f"/api/projects/{rid}/reglas/arnes/repo").json()
    assert (view["harness"]["origin"], view["harness"]["source_path"], view["harness"]["errors"]) == ("repo", "tests/reglas/conftest.py", [])
    # SANDBOX=off: la prueba de humo no se puede correr
    res = client.post(f"/api/projects/{rid}/reglas/arnes/humo")
    assert res.status_code == 409 and res.json()["error"]["code"] == "sandbox_off"
    assert client.delete(f"/api/projects/{rid}/reglas/arnes").json()["harness"] is None


def test_junit_con_entidades_no_se_parsea():
    # El junit.xml sale del sandbox (código del repo): una bomba de entidades no llega al parser
    bomb = '<?xml version="1.0"?><!DOCTYPE t [<!ENTITY a "aaaa">]><testsuite><testcase name="test_humo_api"/></testsuite>'
    result = arnes.read_smoke(bomb, {**OK, "tests": (0, "")})
    assert result.status == "fallo" and result.tests == []


def test_agrega_el_import_que_el_arnes_olvido():
    # Pasó con un arnés de Gemini sobre microblog: `@pytest.fixture` sin `import pytest` (NameError al cargarlo)
    code = "@pytest.fixture\ndef api():\n    return Decimal('1')\n"
    fixed = arnes.add_missing_imports(code)
    assert fixed.startswith("from decimal import Decimal\nimport pytest\n")
    # Lo que ya está importado o definido no se duplica
    ok = "import pytest\n\n@pytest.fixture\ndef api():\n    return 1\n"
    assert arnes.add_missing_imports(ok) == ok
    assert arnes.add_missing_imports("def roto(:") == "def roto(:"
    # Pasó con Clinic-Management-API: `os.environ.setdefault(...)` sin `import os`
    assert arnes.add_missing_imports("os.environ.setdefault('A', 'b')\n").startswith("import os\n")


def test_aviso_de_instalacion_con_la_causa_probable():
    sin_compilador = arnes.install_problem("error: [Errno 2] No such file or directory: 'gcc'")
    assert "SANDBOX_DOCKER_IMAGE=ghcr.io/astral-sh/uv:python3.12-bookworm" in sin_compilador
    antigua = arnes.install_problem("× Failed to build `ruamel-yaml-clib==0.2.6`")
    assert "Python 3.12" in antigua and "SANDBOX_DOCKER_IMAGE" not in antigua
    assert arnes.install_problem("No matching distribution found") == "No se pudieron instalar las dependencias del proyecto: No matching distribution found"


def test_el_validador_avisa_de_nombres_sin_importar():
    # `NameError` al cargar el arnés (os, Callable…): ahora la validación lo ve y la ronda de corrección lo recibe
    tree = ast.parse("import pytest\n\n@pytest.fixture\ndef api():\n    return os.environ.get('A'), Callable, [x for x in range(2)]\n")
    errores = arnes.undefined_names(tree)
    assert sorted(e.split("`")[1] for e in errores) == ["Callable", "os"]
    assert "falta un import" in errores[0]
    # Lo que sí está definido o importado no se marca (comprensiones, `as`, argumentos, star imports)
    ok = ast.parse("from typing import Any\ntry:\n    pass\nexcept ValueError as exc:\n    print(exc)\nwith open('f') as fh:\n    pass\nlambda q: q\n")
    assert arnes.undefined_names(ok) == []
    assert arnes.undefined_names(ast.parse("from x import *\nfoo()\n")) == []
