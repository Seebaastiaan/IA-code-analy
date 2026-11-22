"""
Fase 5 de las reglas verificables (docs/PROPUESTA_REGLAS_VERIFICABLES.md §14): servicios con clientes y calidad.
- Red bloqueada en las pruebas (plugin ia_voy_reglas con IA_VOY_SIN_RED): una llamada sin simular deja la prueba rota.
- Matriz de permisos (app.projects.reglas_matriz): la prueba sale de la tabla, sin IA.
- Evidencia de apoyo (app.projects.reglas_evidencia): solo lugares dentro de los fragmentos que recibió la IA.
- Prueba de fuerza (app.projects.reglas_fuerza + app.analysis.ia_voy_fuerza): detecta la prueba débil sembrada en
  reservas_demo (referencia/pruebas_debiles).
Con `reservas_demo` (Flask + SQLAlchemy): `uv run --with sqlalchemy --with flask pytest tests/test_reglas_calidad.py`.
"""

import dataclasses
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.analyses import mapa, reglas
from app.analysis import clone as clone_mod
from app.analysis import sandbox
from app.assistant import router as assistant_router
from app.assistant.llm import Answer
from app.projects import reglas_arnes as arnes
from app.projects import reglas_evidencia as evidencia
from app.projects import reglas_fuerza as fuerza
from app.projects import reglas_matriz as matriz
from app.projects import reglas_pruebas as pruebas
from tests.conftest import FakeCloner
from tests.test_analysis import URL, wait_done
from tests.test_reglas_arnes import RESERVAS, harness_of
from tests.test_reglas_generadas import OK, PLUGINS, hand_test

SEED_ROOT = RESERVAS.parent
RULES = {r.id: r for r in reglas.parse((RESERVAS / "referencia" / "reglas_negocio.toml").read_text(encoding="utf-8")).rules}
WEAK = (RESERVAS / "referencia" / "pruebas_debiles" / "test_rn004_debil.py").read_text(encoding="utf-8")
# Lo que dice RN-015 (y lo que hace el código del demo, que la cumple)
TEAM = {
    "PATCH /clientes/{cliente_id}": {"admin"},
    "POST /servicios": {"admin"},
    "PATCH /servicios/{servicio_id}": {"admin"},
    "POST /profesionales": {"admin"},
    "GET /profesionales/{profesional_id}/agenda": {"recepcion", "admin"},
    "POST /tareas/recordatorios": {"recepcion", "admin"},
    "GET /reportes/anticipos": {"admin"},
}


def needs_demo() -> None:
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("flask")


@pytest.fixture(scope="module")
def mp() -> mapa.ProjectMap:
    return mapa.build(RESERVAS)


@pytest.fixture(scope="module")
def harness() -> str:
    return harness_of(RESERVAS)


def copy_demo(work: Path, overlay: dict[str, str]) -> Path:
    """La copia del repo como en el sandbox (sin las pruebas de referencia), con los archivos de IA voy encima."""
    shutil.copytree(RESERVAS, work, ignore=shutil.ignore_patterns("__pycache__", "*.db", "reglas", "referencia"))
    for rel, text in overlay.items():
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        (work / rel).write_text(text, encoding="utf-8")
    return work


def env(out: Path | None = None) -> dict[str, str]:
    e = {**os.environ, "PYTHONPATH": str(PLUGINS), "PYTHONDONTWRITEBYTECODE": "1", "IA_VOY_SIN_RED": "1"}
    if out is not None:
        e["IA_VOY_REGLAS_OUT"] = str(out)
    return e


def run_tests(work: Path, harness: str, files: dict[str, str]) -> dict | None:
    """Modo `pruebas` del sandbox, aquí."""
    copy_demo(work, pruebas.overlay(harness, files))
    out = work.parent / "reglas.json"
    subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", "-p", "ia_voy_reglas", pruebas.DIR],
        cwd=work, env=env(out), capture_output=True, text=True, timeout=300, check=False,
    )
    return json.loads(out.read_text(encoding="utf-8")) if out.exists() else None


def run_strength(work: Path, harness: str, objectives: list[tuple[str, str, str, list[fuerza.Mutant]]]) -> dict | None:
    """Modo `fuerza` del sandbox, aquí: (regla, archivo, código de la prueba, mutantes)."""
    files = {path: code for _, path, code, _ in objectives}
    spec = fuerza.spec([(rid, path, ms) for rid, path, _, ms in objectives])
    copy_demo(work, {**pruebas.overlay(harness, files), fuerza.SPEC: json.dumps(spec)})
    out = work.parent / "fuerza.json"
    subprocess.run([sys.executable, str(sandbox.STRENGTH), fuerza.SPEC, str(out)], cwd=work, env=env(), capture_output=True, text=True, timeout=600, check=False)
    return json.loads(out.read_text(encoding="utf-8")) if out.exists() else None


# ───────────────────────── Red bloqueada (§7.3) ─────────────────────────


def test_la_red_queda_bloqueada_y_la_prueba_rota(tmp_path):
    (tmp_path / "test_red.py").write_text(
        "import socket\nimport pytest\n\n"
        "@pytest.mark.regla('RN-001')\ndef test_sale_a_internet():\n    socket.create_connection(('example.com', 80), timeout=1)\n\n"
        "@pytest.mark.regla('RN-002')\ndef test_el_codigo_atrapa_el_error():\n    try:\n        socket.getaddrinfo('api.stripe.com', 443)\n"
        "    except Exception:\n        pass\n\n"
        "@pytest.mark.regla('RN-003')\ndef test_lo_local_si():\n    s = socket.socket()\n    try:\n        s.connect_ex(('127.0.0.1', 9))\n    finally:\n        s.close()\n",
        encoding="utf-8",
    )
    out = tmp_path / "reglas.json"
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "ia_voy_reglas"], cwd=tmp_path, env=env(out), capture_output=True, check=False, timeout=60)
    data = json.loads(out.read_text(encoding="utf-8"))
    by_rule = {t["rules"][0]: t for t in data["tests"]}
    # Salir a la red deja la prueba rota, también si el código atrapó el error y la prueba «pasó»
    assert {r: (t["outcome"], t["exception"]) for r, t in by_rule.items()} == {
        "RN-001": ("failed", "RedBloqueada"), "RN-002": ("failed", "RedBloqueada"), "RN-003": ("passed", ""),
    }
    assert "example.com:80" not in by_rule["RN-001"]["message"] or "salir a la red" in by_rule["RN-001"]["message"]
    assert {t.rules[0]: t.outcome for t in reglas.plugin_tests(data)} == {"RN-001": "broken", "RN-002": "broken", "RN-003": "passed"}


def test_sin_la_variable_no_se_bloquea_nada(tmp_path):
    (tmp_path / "test_x.py").write_text("import socket\n\ndef test_rn001_x():\n    assert socket.getaddrinfo is not None\n", encoding="utf-8")
    out = tmp_path / "reglas.json"
    e = {**env(out)}
    e.pop("IA_VOY_SIN_RED")
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "ia_voy_reglas"], cwd=tmp_path, env=e, capture_output=True, check=False, timeout=60)
    assert json.loads(out.read_text(encoding="utf-8"))["tests"][0]["outcome"] == "passed"


def test_el_sandbox_instala_las_librerias_y_bloquea_la_red():
    assert "time-machine freezegun respx responses aiosqlite" in sandbox.SCRIPT
    assert sandbox.SCRIPT.count("IA_VOY_SIN_RED=1") == 3  # arnés/pruebas, fuerza y las aprobadas en el análisis
    assert '"$MODE" = fuerza' in sandbox.SCRIPT and "ia_voy_fuerza.py" in sandbox.SCRIPT


def test_avisos_del_arnes_para_pagos_y_http(mp, harness):
    pagos = dataclasses.replace(mp, integrations=[*mp.integrations, mapa.Integration("pagos", "stripe", "reservas/app.py", 1)])
    assert any("no tiene `pagos`" in w for w in arnes.validate(harness, pagos).warnings)
    http = dataclasses.replace(mp, integrations=[*mp.integrations, mapa.Integration("http", "httpx", "reservas/app.py", 1)])
    assert any("no usa `respx` ni `responses`" in w for w in arnes.validate(harness, http).warnings)
    assert not any("respx" in w for w in arnes.validate(harness + "\nimport respx\n", http).warnings)


# ───────────────────────── Matriz de permisos (§6.3) ─────────────────────────


def test_la_matriz_sale_del_mapa_con_las_celdas_vacias(mp):
    m = matriz.propose(mp)
    assert m.roles == ["cliente", "recepcion", "admin"]
    ids = [a.id for a in m.actions]
    # Lo que escribe con usuario o lo que solo algunos roles pueden; ni el login ni el alta de clientes
    assert set(TEAM) <= set(ids) and "POST /citas" in ids and "POST /login" not in ids and "GET /citas" not in ids
    agenda = next(a for a in m.actions if a.id == "GET /profesionales/{profesional_id}/agenda")
    # Lo que hace el código es solo una sugerencia: el oráculo es la regla
    assert agenda.suggested == ["recepcion", "admin"] and agenda.cells == {}
    assert matriz.looks_like_permissions(RULES["RN-015"]) and not matriz.looks_like_permissions(RULES["RN-004"])


def team_cells(mp, changes: dict[str, dict[str, str]] | None = None) -> dict:
    roles = matriz.propose(mp).roles
    cells = {a: {r: "permitido" if r in ok else "prohibido" for r in roles} for a, ok in TEAM.items()}
    for action, override in (changes or {}).items():
        cells[action].update(override)
    return cells


def test_errores_de_la_matriz(mp):
    with pytest.raises(matriz.MatrixError, match="no es una acción"):
        matriz.update(mp, {"POST /inventada": {"admin": "permitido"}})
    with pytest.raises(matriz.MatrixError, match="no es un rol"):
        matriz.update(mp, {"POST /servicios": {"gerente": "permitido"}})
    with pytest.raises(matriz.MatrixError) as exc:
        matriz.test_code(RULES["RN-015"], matriz.update(mp, {"POST /servicios": {"admin": None}}), mp.framework)
    assert exc.value.code == "empty_matrix"


def test_la_prueba_de_la_matriz_es_determinista_y_valida(mp, harness):
    m = matriz.update(mp, team_cells(mp))
    code = matriz.test_code(RULES["RN-015"], m, mp.framework)
    assert code == matriz.test_code(RULES["RN-015"], matriz.update(mp, team_cells(mp)), mp.framework)
    check = pruebas.validate(code, "RN-015", mp, arnes.fixtures_of(harness))
    assert check.valid and check.tests == ["test_rn015_matriz_de_permisos"], check.errors
    assert len(m.cases()) == 21 and "('POST /servicios', 'cliente', False)" in code
    # Guardada y vuelta a leer sobre el mapa de hoy: se conservan las celdas
    assert matriz.from_dict(m.to_dict(), mp).cases() == m.cases()
    assert "json={}" in code and 'format="json"' in matriz.test_code(RULES["RN-015"], m, "django")


def test_la_matriz_del_equipo_cumple_y_detecta_un_permiso_de_mas(tmp_path, mp, harness):
    needs_demo()
    path = pruebas.test_path(RULES["RN-015"])
    ok = matriz.test_code(RULES["RN-015"], matriz.update(mp, team_cells(mp)), mp.framework)
    results = pruebas.read_run(run_tests(tmp_path / "a", harness, {path: ok}), OK, [RULES["RN-015"]])
    assert results["RN-015"].verdict == "cumple", results["RN-015"]
    # El equipo dice que el cliente sí puede crear servicios: el código lo rechaza (403) → no cumple
    wrong = matriz.test_code(RULES["RN-015"], matriz.update(mp, team_cells(mp, {"POST /servicios": {"cliente": "permitido"}})), mp.framework)
    results = pruebas.read_run(run_tests(tmp_path / "b", harness, {path: wrong}), OK, [RULES["RN-015"]])
    assert results["RN-015"].verdict == "no_cumple" and any("cliente debería poder POST /servicios" in t.message for t in results["RN-015"].tests)


def test_un_404_de_un_rol_prohibido_deja_la_prueba_rota(tmp_path, mp, harness):
    """Si el código busca el registro antes de revisar el permiso no se puede saber: rota, no «no cumple»."""
    needs_demo()
    cells = {"POST /citas/{cita_id}/cancelar": {"recepcion": "prohibido"}}
    code = matriz.test_code(RULES["RN-015"], matriz.update(mp, cells), mp.framework)
    results = pruebas.read_run(run_tests(tmp_path / "r", harness, {pruebas.test_path(RULES["RN-015"]): code}), OK, [RULES["RN-015"]])
    assert results["RN-015"].verdict == "prueba_rota" and "busca el registro antes de revisar el permiso" in results["RN-015"].tests[0].message


# ───────────────────────── Evidencia de apoyo (§8) ─────────────────────────


class FakeLLM:
    def __init__(self, data: dict) -> None:
        self.data = data
        self.calls: list[str] = []

    def answer(self, system, turns, schema, on_delta=None) -> Answer:
        self.calls.append(turns[0].text)
        return Answer(self.data, "Gemini 3.8 Flash")


def test_evidencia_solo_con_lugares_de_los_fragmentos(mp):
    frags, search = evidencia.fragments(RESERVAS, mp, RULES["RN-004"])
    assert search == ["palabras"] and frags and not any(f.file.startswith("tests/") for f in frags)
    cita = next(i for i, f in enumerate(frags, 1) if f.file == "reservas/citas.py" and f.start <= 51 <= f.end)
    llm = FakeLLM({
        "lectura": "implementada", "resumen": "Se rechaza con menos de 2 h.",
        "lugares": [
            {"fragmento": cita, "desde": 51, "hasta": 52, "por_que": "aquí se rechaza"},
            {"fragmento": 99, "desde": 1, "hasta": 2, "por_que": "inventado"},
            {"fragmento": cita, "desde": 5000, "hasta": 5001, "por_que": "fuera del fragmento"},
        ],
    })
    ev = evidencia.collect(llm, RESERVAS, mp, RULES["RN-004"])
    assert (ev.verdict, ev.model, [(p.file, p.start, p.end) for p in ev.places]) == ("implementada", "Gemini 3.8 Flash", [("reservas/citas.py", 51, 52)])
    assert "id: RN-004" in llm.calls[0] and "   51  " in llm.calls[0]
    assert evidencia.loads(json.dumps(ev.to_dict())) == ev
    # Sin lugares válidos no puede decir que está implementada
    assert evidencia.collect(FakeLLM({"lectura": "parcial", "resumen": "x", "lugares": []}), RESERVAS, mp, RULES["RN-004"]).verdict == "no_encontrada"


def test_evidencia_sin_fragmentos_no_llama_a_la_ia(tmp_path):
    rule = reglas.BusinessRule(id="RN-001", title="Zzzz qqqq", description="Wwww xxxx", severity="baja")
    llm = FakeLLM({})
    ev = evidencia.collect(llm, tmp_path, mapa.build(tmp_path), rule)
    assert ev.verdict == "no_encontrada" and llm.calls == []


# ───────────────────────── Prueba de fuerza ─────────────────────────


def test_no_se_muta_la_linea_de_otra_regla():
    # RN-016 de inventario: su evidencia es la función `salida`, que también trae el aviso de RN-014 (`base < costo`).
    # Antes solo se mutaba esa línea (la de otra regla) y la prueba buena salía «débil»
    inventario = SEED_ROOT / "inventario_demo"
    reglas_inv = reglas.parse((inventario / "referencia" / "reglas_negocio.toml").read_text(encoding="utf-8")).rules
    rn016 = next(r for r in reglas_inv if r.id == "RN-016")
    ev = evidencia.Evidence("implementada", "", [evidencia.Place("inventario/servicios.py", 43, 54, "")])
    mp_inv = mapa.build(inventario)

    sin_otras, _ = fuerza.mutants(inventario, mp_inv, rn016, [], ev)
    assert {m.line for m in sin_otras} == {45, 46, 47}  # sin saber de las otras reglas, 47 también entra
    con_otras, _ = fuerza.mutants(inventario, mp_inv, rn016, [], ev, others=reglas_inv)
    assert {m.line for m in con_otras} == {45, 46} and all(m.kind == "aritmetica" for m in con_otras)
    # La línea del aviso (47) es de RN-014: con las demás reglas a la vista, nadie la muta por RN-016
    assert 47 not in {m.line for m in con_otras}


def test_mutantes_dirigidos_a_las_lineas_de_la_regla(mp):
    ms, found = fuerza.mutants(RESERVAS, mp, RULES["RN-004"], ["POST /citas"])
    assert [t.source for t in found][:2] == ["endpoint", "llamada"] and any(t.file == "reservas/citas.py" for t in found)
    assert [(m.file, m.line, m.kind) for m in ms] == [
        ("reservas/citas.py", 51, "comparacion"), ("reservas/citas.py", 51, "condicion"), ("reservas/citas.py", 52, "excepcion"),
    ]
    assert ms[0].description == "`inicio - ahora < ANTICIPACION_MINIMA` → `inicio - ahora <= ANTICIPACION_MINIMA`"
    for m in ms:
        compile(m.code, m.file, "exec")
    # Deterministas
    assert [m.code for m in fuerza.mutants(RESERVAS, mp, RULES["RN-004"], ["POST /citas"])[0]] == [m.code for m in ms]
    # Con evidencia se mutan sus líneas
    ev = evidencia.Evidence("implementada", "", [evidencia.Place("reservas/auth.py", 29, 31, "")])
    ms2, found2 = fuerza.mutants(RESERVAS, mp, RULES["RN-014"], [], ev)
    assert {t.source for t in found2} == {"evidencia"} and {m.line for m in ms2} <= {29, 30, 31} and ms2


def test_mutar_respeta_los_acentos_de_la_linea():
    source = (
        '@app.post("/x")\n@requiere("admin")\ndef f(x, precio):\n    if "acción" and x > 3:\n        raise ValueError("número")\n'
        '    log.info("x")\n    correo.enviar("a", "b")\n    total = precio * PORCENTAJE\n    resta = x - precio\n'
        '    return 1 if x.premium else 2\n'
    )
    import ast

    out = fuerza.candidates(source, ast.parse(source), 1, 10)
    kinds = {c.kind for c in out}
    assert set(fuerza.KINDS) <= kinds
    described = {c.description for c in out}
    # El decorador de permiso sí, el de la ruta no; la llamada al correo sí, el registro no; la cuenta con una
    # constante sí, la resta de dos variables no (puede ser de fechas: cambiarla solo rompería el código)
    assert 'se quita `@requiere("admin")`' in described and not any("app.post" in d for d in described)
    assert any("correo.enviar" in d for d in described) and not any("log.info" in d for d in described)
    assert "`precio * PORCENTAJE` → `precio / PORCENTAJE`" in described and not any("x - precio" in d for d in described)
    assert "se invierte la condición `x.premium`" in described
    lines = fuerza._byte_lines(source)
    for c in out:
        code = fuerza._drop_line(lines, c.node) if c.kind == "decorador" else fuerza._splice(lines, c.node, c.new)
        compile(code, "x.py", "exec")
        assert code.count("\n") == source.count("\n")


def test_si_la_evidencia_no_tiene_que_mutar_se_amplia_a_su_funcion(mp):
    # RN-006: la evidencia señala la creación de la cita (una asignación en varias líneas, sin nada que cambiar)
    ev = evidencia.Evidence("implementada", "", [evidencia.Place("reservas/citas.py", 66, 67, "")])
    ms, found = fuerza.mutants(RESERVAS, mp, RULES["RN-006"], [], ev)
    assert found[0].source == "evidencia+funcion" and any(m.kind == "aritmetica" and "PORCENTAJE_ANTICIPO" in m.description for m in ms)


def test_la_evidencia_busca_la_logica_fuera_de_los_endpoints(mp):
    """citas.cancelar (donde está el error de RN-007) no es un endpoint: debe llegar a la IA."""
    frags, _ = evidencia.fragments(RESERVAS, mp, RULES["RN-007"])
    assert any(f.file == "reservas/citas.py" and f.start <= 87 <= f.end for f in frags)


def test_la_prueba_de_fuerza_detecta_la_prueba_debil(tmp_path, mp, harness):
    """Criterio de aceptación de la fase 5: la prueba débil sembrada sale débil y la buena sale fuerte."""
    needs_demo()
    ms, found = fuerza.mutants(RESERVAS, mp, RULES["RN-004"], ["POST /citas"])
    weak_ms = [dataclasses.replace(m, id=m.id + "-d") for m in ms]
    strong = hand_test("RN-004", RESERVAS)
    data = run_strength(tmp_path / "repo", harness, [
        ("RN-004", f"{pruebas.DIR}/test_rn004_buena.py", strong, ms),
        ("RN-004-D", f"{pruebas.DIR}/test_rn004_debil.py", WEAK, weak_ms),
    ])
    for o in data["objetivos"]:
        assert o["base"] == 0, o  # las dos pasan con el código actual
    plan = {"RN-004": (ms, found), "RN-004-D": (weak_ms, found)}
    results = fuerza.read(data, OK, plan)
    assert (results["RN-004"].status, results["RN-004"].killed, results["RN-004"].total) == ("fuerte", 3, 3)
    weak = results["RN-004-D"]
    assert (weak.status, weak.killed, weak.total) == ("debil", 0, 3) and "verifica lo que dice la regla" in weak.detail
    assert [s.line for s in weak.survivors] == [51, 51, 52]
    # El archivo original quedó como estaba después de mutarlo
    assert (tmp_path / "repo" / "reservas" / "citas.py").read_text(encoding="utf-8") == (RESERVAS / "reservas" / "citas.py").read_text(encoding="utf-8")


def test_resultado_de_la_prueba_de_fuerza_sin_correr():
    m = fuerza.Mutant("RN-001-1", "a.py", 1, "comparacion", "x", "")
    t = [fuerza.Target("a.py", 1, 2, "endpoint")]
    plan = {"RN-001": ([m], t), "RN-002": ([], t)}
    roto = fuerza.read(None, {"venv": (0, ""), "install": (1, "ERROR: x not found"), "tests": (None, "")}, plan)
    assert roto["RN-001"].status == "no_aplica" and "No se pudieron instalar" in roto["RN-001"].detail
    data = {"objetivos": [{"regla": "RN-001", "base": 1, "mutantes": []}]}
    res = fuerza.read(data, OK, plan)
    assert res["RN-001"].status == "no_aplica" and "no pasa con el código actual" in res["RN-001"].detail
    assert res["RN-002"].status == "no_aplica" and "evidencia" in res["RN-002"].detail
    # Solo corrió 1 de los 2 mutantes y la prueba no lo notó: es poca base para llamarla débil
    m2 = dataclasses.replace(m, id="RN-001-2")
    uno = fuerza.read({"objetivos": [{"regla": "RN-001", "base": 0, "mutantes": [{"id": "RN-001-1", "codigo_salida": 0}]}]}, OK, {"RN-001": ([m, m2], t)})
    assert (uno["RN-001"].status, uno["RN-001"].killed, uno["RN-001"].total) == ("parcial", 0, 1)
    dos = fuerza.read({"objetivos": [{"regla": "RN-001", "base": 0, "mutantes": [{"id": "RN-001-1", "codigo_salida": 0}, {"id": "RN-001-2", "codigo_salida": 0}]}]}, OK, {"RN-001": ([m, m2], t)})
    assert dos["RN-001"].status == "debil"
    assert fuerza.loads(json.dumps(dos["RN-001"].to_dict())) == dos["RN-001"]


# ───────────────────────── Endpoints (reservas_demo de punta a punta) ─────────────────────────


class ClonerReservas(FakeCloner):
    def clone(self, settings, repo_id, url, branch, token, attempt):
        result = super().clone(settings, repo_id, url, branch, token, attempt)
        tmp = clone_mod.clones_root(settings) / f"{repo_id}.tmp-{attempt}"
        shutil.copytree(RESERVAS, tmp, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.db"))
        return result


@pytest.fixture
def cloner() -> ClonerReservas:
    return ClonerReservas()


class LocalRunner:
    """Sustituye a WSL/Docker en los modos `arnes`, `pruebas` y `fuerza`: lo mismo, con el Python de las pruebas."""

    def __init__(self, settings, repo_id: str, mode: str, overlay: dict[str, str]):
        self.work = clone_mod.clones_root(settings) / f"{repo_id}.{mode}-local"
        shutil.rmtree(self.work, ignore_errors=True)
        repo = self.work / "repo"
        shutil.copytree(clone_mod.clone_dir(settings, repo_id), repo, ignore=shutil.ignore_patterns("referencia"))
        for rel, text in overlay.items():
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text(text, encoding="utf-8")
        if mode == "fuerza":
            cmd = [sys.executable, str(sandbox.STRENGTH), fuerza.SPEC, str(self.work / "fuerza.json")]
        else:
            target = arnes.SMOKE if mode == "arnes" else pruebas.DIR
            cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", "-p", "ia_voy_reglas",
                   f"--junitxml={self.work / 'junit.xml'}", "-o", "junit_family=xunit1", target]
        proc = subprocess.run(cmd, cwd=repo, env=env(self.work / "reglas.json"), capture_output=True, text=True, timeout=600, check=False)
        self.code, self.log = proc.returncode, proc.stdout + proc.stderr

    async def wait(self, name: str) -> sandbox.PhaseResult:
        return sandbox.PhaseResult(name, self.code if name == "tests" else 0, self.log if name == "tests" else "")

    def output(self) -> sandbox.SandboxOutput:
        def read(name):
            p = self.work / name
            return p.read_text(encoding="utf-8") if p.exists() else None

        reglas_json, fuerza_json = read("reglas.json"), read("fuerza.json")
        return sandbox.SandboxOutput(
            junit=read("junit.xml"), reglas=json.loads(reglas_json) if reglas_json else None, fuerza=json.loads(fuerza_json) if fuerza_json else None,
        )

    def close(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)


@pytest.fixture
def local_sandbox(settings, monkeypatch):
    settings.sandbox = "wsl"
    modes: list[str] = []

    def start(settings_, repo_id, mode="analisis", overlay=None):
        modes.append(mode)
        if mode == "analisis":
            return None, "sin sandbox en las pruebas"
        return LocalRunner(settings_, repo_id, mode, overlay or {}), None

    monkeypatch.setattr(sandbox, "start", start)
    monkeypatch.setattr(sandbox, "_available", lambda s: None)
    return modes


def wait_free(client, rid: str) -> dict:
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        view = client.get(f"/api/projects/{rid}/reglas/pruebas").json()
        if view["busy"] is None:
            return view
        time.sleep(0.2)
    raise AssertionError("no terminó")


def ready_project(client) -> str:
    """Proyecto con reservas_demo, sus reglas en la app y el arnés del repo aprobado."""
    rid = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])["repo_id"]
    assert client.put(f"/api/projects/{rid}/reglas", json={"content": (RESERVAS / "referencia/reglas_negocio.toml").read_text(encoding="utf-8")}).status_code == 200
    client.post(f"/api/projects/{rid}/reglas/arnes/repo")
    client.post(f"/api/projects/{rid}/reglas/arnes/humo")
    deadline = time.monotonic() + 120
    while client.get(f"/api/projects/{rid}/reglas/arnes").json()["harness"]["smoke"] == "corriendo" and time.monotonic() < deadline:
        time.sleep(0.2)
    assert client.post(f"/api/projects/{rid}/reglas/arnes/aprobar").json()["ready"]
    return rid


def rows(view: dict) -> dict[str, dict]:
    return {r["id"]: r for r in view["rules"]}


class RuleLLM:
    """Gemini falso: para pruebas responde con las escritas a mano del demo; para evidencia, con citas.py:51-52."""

    def __init__(self, tests: dict[str, dict]) -> None:
        self.tests = tests

    def answer(self, system, turns, schema, on_delta=None) -> Answer:
        text = turns[0].text
        rid = text.split("id: ", 1)[1].split("\n", 1)[0]
        if "lugares" in schema["properties"]:
            n = next(i for i, chunk in enumerate(text.split("FRAGMENTO ")[1:], 1) if chunk.split(" · ", 1)[1].startswith("reservas/citas.py") and "   51  " in chunk)
            return Answer({"lectura": "implementada", "resumen": "Rechaza con menos de 2 h", "lugares": [{"fragmento": n, "desde": 51, "hasta": 52, "por_que": "aquí"}]}, "Gemini 3.8 Flash")
        return Answer(self.tests[rid], "Gemini 3.8 Flash")

    def embed(self, texts, task="RETRIEVAL_DOCUMENT"):
        raise AssertionError("sin índice no se piden embeddings")


def test_matriz_evidencia_y_fuerza_de_punta_a_punta(client, settings, local_sandbox):
    needs_demo()
    settings.gemini_api_key = "clave"
    llm = RuleLLM({"RN-004": {"tipo": "datos", "implementada": True, "endpoints": ["POST /citas"], "codigo": WEAK, "supuestos": []}})
    client.app.dependency_overrides[assistant_router.get_llm] = lambda: llm
    rid = ready_project(client)
    view = client.get(f"/api/projects/{rid}/reglas/pruebas").json()
    assert view["can_explain"] and rows(view)["RN-015"]["permissions"] and not rows(view)["RN-004"]["permissions"]

    # Matriz: vacía con sugerencias; al guardarla sale la prueba (sin IA), que corre y se aprueba como cualquier otra
    m = client.get(f"/api/projects/{rid}/reglas/pruebas/RN-015/matriz").json()
    assert m["roles"] == ["cliente", "recepcion", "admin"] and not m["saved"] and all(a["cells"] == {} for a in m["actions"])
    bad = client.put(f"/api/projects/{rid}/reglas/pruebas/RN-015/matriz", json={"cells": {"POST /x": {"admin": "permitido"}}})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "unknown_action"
    cells = {a: {r: "permitido" if r in ok else "prohibido" for r in m["roles"]} for a, ok in TEAM.items()}
    row = rows(client.put(f"/api/projects/{rid}/reglas/pruebas/RN-015/matriz", json={"cells": cells}).json())["RN-015"]
    assert (row["state"], row["test"]["origin"], row["test"]["tipo"], row["test"]["has_matrix"]) == ("borrador", "matriz", "permisos", True)
    assert client.get(f"/api/projects/{rid}/reglas/pruebas/RN-015/matriz").json()["saved"]

    # La prueba débil de RN-004 (como si la hubiera escrito la IA), y las dos corren en el sandbox
    client.post(f"/api/projects/{rid}/reglas/pruebas", json={"ids": ["RN-004"]})
    wait_free(client, rid)
    client.post(f"/api/projects/{rid}/reglas/pruebas/correr", json={})
    view = wait_free(client, rid)
    assert {i: rows(view)[i]["test"]["run"]["verdict"] for i in ("RN-004", "RN-015")} == {"RN-004": "cumple", "RN-015": "cumple"}
    assert rows(view)["RN-004"]["test"]["strength_blocked"] is None

    # Evidencia: dónde está implementada (no cambia el estado)
    row = rows(client.post(f"/api/projects/{rid}/reglas/pruebas/RN-004/evidencia").json())["RN-004"]
    assert row["evidence"]["verdict"] == "implementada" and row["evidence"]["places"][0]["start"] == 51 and not row["evidence"]["stale"]
    assert row["state"] == "borrador"

    # Prueba de fuerza: con la evidencia se mutan citas.py:51-52 y la prueba débil no nota nada
    assert client.post(f"/api/projects/{rid}/reglas/pruebas/fuerza", json={"ids": ["RN-004"]}).json()["busy"]["kind"] == "fuerza"
    view = wait_free(client, rid)
    test = rows(view)["RN-004"]["test"]
    assert (test["strength_status"], test["strength"]["status"], test["strength"]["source"]) == ("hecho", "debil", "evidencia"), test["strength"]
    assert "fuerza" in local_sandbox
    # Editarla invalida la prueba de fuerza
    fixed = client.put(f"/api/projects/{rid}/reglas/pruebas/RN-004", json={"code": hand_test("RN-004", RESERVAS)}).json()
    assert rows(fixed)["RN-004"]["test"]["strength"] is None and rows(fixed)["RN-004"]["test"]["strength_status"] == "pendiente"
    res = client.post(f"/api/projects/{rid}/reglas/pruebas/fuerza", json={"ids": ["RN-004"]})
    assert res.status_code == 409 and res.json()["error"]["code"] == "nothing_to_test"  # hay que correrla primero
