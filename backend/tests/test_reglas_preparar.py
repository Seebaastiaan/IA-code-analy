"""«Preparar todo» en el servidor (app.projects.preparar): corre sin la pestaña abierta y se detiene diciendo por qué."""

import asyncio
import time
from types import SimpleNamespace as NS

import pytest

from app.projects import preparar
from tests.test_analysis import URL, wait_done
from tests.test_reglas_v2 import V2

SIN_DUDAS = V2 + '''
[[regla]]
id          = "RN-004"
titulo      = "El SKU es único"
descripcion = "No hay dos productos con el mismo SKU."
severidad   = "alta"
tipo        = "datos"
estado      = "borrador"
dudas       = []
'''


@pytest.fixture
def rid(client) -> str:
    return wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])["repo_id"]


def esperar(client, repo_id: str) -> dict:
    for _ in range(200):
        body = client.get(f"/api/projects/{repo_id}/reglas/preparar").json()
        if not body["running"]:
            return body
        time.sleep(0.05)
    raise AssertionError("«Preparar todo» no terminó")


def pasos(body: dict) -> dict[str, tuple[str, str | None]]:
    return {s["id"]: (s["status"], s["note"]) for s in body["steps"]}


def test_sin_reglas_se_detiene_en_el_primer_paso(client, rid):
    antes = client.get(f"/api/projects/{rid}/reglas/preparar").json()
    assert antes["running"] is False and antes["started_at"] is None and len(antes["steps"]) == 7

    assert client.post(f"/api/projects/{rid}/reglas/preparar").status_code == 200
    body = esperar(client, rid)
    assert pasos(body)["reglas"] == ("fallo", "Todavía no hay reglas: sube el documento de requisitos o escribe una regla.")
    assert pasos(body)["arnes"][0] == "pendiente" and body["summary"] is None and body["finished_at"]


def test_aprueba_las_reglas_sin_dudas_y_se_detiene_donde_falta_la_ia(client, rid):
    assert client.put(f"/api/projects/{rid}/reglas", json={"content": SIN_DUDAS}).status_code == 200
    client.post(f"/api/projects/{rid}/reglas/preparar")
    body = esperar(client, rid)

    # RN-004 no tenía dudas: la aprobó el programa; RN-002 espera la decisión del equipo
    assert pasos(body)["reglas"] == ("hecho", "3 aprobadas · 1 esperan tu decisión (tienen dudas)")
    rules = {r["id"]: r for r in client.get(f"/api/projects/{rid}/reglas").json()["uploaded"]["rules"]}
    assert rules["RN-004"]["status"] == "aprobada" and rules["RN-002"]["status"] == "borrador"

    # Sin clave de la IA ni conftest.py en el repo no hay arnés: se dice cómo resolverlo
    status, note = pasos(body)["arnes"]
    assert status == "fallo" and "clave de la IA" in note


def test_detener_sin_nada_corriendo_y_de_otro_equipo(client, rid, fake):
    assert client.delete(f"/api/projects/{rid}/reglas/preparar").json()["running"] is False
    assert client.get("/api/projects/no-existe/reglas/preparar").status_code == 404


# ─── El flujo completo con las rutas simuladas (sin sandbox ni IA reales) ───


def _test(verdict: str, strength: str, approved: bool = False) -> NS:
    return NS(
        kind="prueba", origin="ia", errors=[], outdated=False, gone_endpoints=[], run_status="hecho", run=NS(verdict=verdict), strength_status="hecho",
        strength_blocked=None, strength=NS(status=strength) if strength else None, approved=approved, blocked=None,
    )


def _row(rule_id: str, verdict: str, strength: str, cross: str) -> NS:
    return NS(id=rule_id, test=_test(verdict, strength), evidence=None, crosscheck=NS(status=cross))


class Rutas:
    """Lo mínimo de las rutas de reglas, arnés y pruebas que usa el flujo."""

    def __init__(self, fixes: bool = False) -> None:
        # fixes = escribir la prueba de nuevo hace que coincida con la lectura del código
        self.fixes = fixes
        self.generated: list[list[str]] = []
        self.ran: list[list[str]] = []
        self.approved_tests: list[str] = []
        self.explained: list[str] = []
        # RN-002 falla y la lectura del código tampoco encuentra la regla: no tiene prueba de fuerza (solo se mide a las que pasan)
        self.rows = [_row("RN-001", "cumple", "fuerte", "coincide"), _row("RN-002", "no_cumple", None, "coincide"),
                     _row("RN-003", "cumple", "debil", "coincide"), _row("RN-004", "cumple", "fuerte", "discrepa")]
        self._running: dict = {}
        self._busy: dict = {}
        self.Ids = lambda ids=None: NS(ids=ids)
        self.RuleStates = lambda **kw: NS(**kw)

    def get_rules(self, *a):
        rules = [NS(id=r.id, status="aprobada", doubts=[]) for r in self.rows]
        return NS(active="app", uploaded=NS(valid=True, rules=rules), repo=None)

    def get_harness(self, *a):
        return NS(cloned=True, repo_harness=None, can_generate=True, sandbox=True,
                  harness=NS(origin="ia", smoke="paso", approved=True, smoke_message=None))

    def list_tests(self, *a):
        return NS(rules=self.rows, can_generate=True, can_explain=True, messages=[])

    async def explain_rule(self, repo_id, rule_id, *a):
        self.explained.append(rule_id)
        next(r for r in self.rows if r.id == rule_id).evidence = NS(stale=False)

    def approve_tests(self, repo_id, body, *a):
        self.approved_tests = body.ids

    def generate_tests(self, repo_id, body, *a):
        self.generated.append(body.ids)
        if self.fixes:
            for r in self.rows:
                if r.id in body.ids:
                    r.crosscheck = NS(status="coincide")

    def run_tests(self, repo_id, body, *a):
        self.ran.append(body.ids)

    def strength_tests(self, repo_id, body, *a):
        pass


def test_aprueba_solas_solo_las_pruebas_fuertes_que_coinciden_con_la_lectura(monkeypatch):
    fake = Rutas()
    for name in ("rule_routes", "harness_routes", "test_routes"):
        monkeypatch.setattr(preparar, name, fake)
    monkeypatch.setattr(preparar.db, "session", lambda path: _NoConn())
    job = preparar.Job(user_id="u1")
    asyncio.run(preparar._work(preparar.Flow(NS(database_path=""), "r1", job, llm=object())))

    assert job.summary == preparar.DONE and not job.running
    assert fake.explained == ["RN-001", "RN-002", "RN-003", "RN-004"]
    # RN-004 no coincidía: se escribió y corrió una vez más, y como sigue sin coincidir queda para el equipo con RN-003 (débil)
    assert fake.generated == [["RN-004"]] and fake.ran == [["RN-004"]]
    assert fake.approved_tests == ["RN-001", "RN-002"]
    nota = {s.id: s.note for s in job.steps}
    assert nota["correr"] == "3 cumplen · 1 no cumplen · 0 con prueba rota"
    assert nota["fuerza"] == "1 pruebas flojas para revisar"
    assert nota["revision"].startswith("2 pruebas aprobadas por el programa · 1 escritas de nuevo por no coincidir (0 ya están bien) · 1 no coinciden")


def test_una_prueba_que_no_coincide_se_escribe_de_nuevo_y_si_ahora_coincide_se_aprueba(monkeypatch):
    fake = Rutas(fixes=True)
    for name in ("rule_routes", "harness_routes", "test_routes"):
        monkeypatch.setattr(preparar, name, fake)
    monkeypatch.setattr(preparar.db, "session", lambda path: _NoConn())
    job = preparar.Job(user_id="u1")
    asyncio.run(preparar._work(preparar.Flow(NS(database_path=""), "r1", job, llm=object())))
    assert fake.approved_tests == ["RN-001", "RN-002", "RN-004"]
    assert "1 escritas de nuevo por no coincidir (1 ya están bien)" in {s.id: s.note for s in job.steps}["revision"]


def test_detener_deja_el_paso_en_curso_pendiente(monkeypatch):
    fake = Rutas()
    for name in ("rule_routes", "harness_routes", "test_routes"):
        monkeypatch.setattr(preparar, name, fake)
    monkeypatch.setattr(preparar.db, "session", lambda path: _NoConn())
    job = preparar.Job(user_id="u1")
    job.cancelled = True
    asyncio.run(preparar._work(preparar.Flow(NS(database_path=""), "r1", job, llm=None)))
    estados = {s.id: s.status for s in job.steps}
    assert estados["reglas"] == "hecho" and estados["arnes"] == "pendiente" and job.summary is None


class _NoConn:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


def test_una_prueba_rota_se_escribe_de_nuevo_y_una_que_falla_y_coincide_se_aprueba(monkeypatch):
    fake = Rutas()
    rota = _row("RN-005", "prueba_rota", None, "sin_revisar")
    fake.rows.append(rota)

    def generate(repo_id, body, *a):
        fake.generated.append(body.ids)
        if "RN-005" in body.ids:
            # Corregida con el error a la vista: ahora falla por el código y la lectura lo confirma
            rota.test = _test("no_cumple", None)
            rota.crosscheck = NS(status="coincide")
            rota.evidence = None

    fake.generate_tests = generate
    for name in ("rule_routes", "harness_routes", "test_routes"):
        monkeypatch.setattr(preparar, name, fake)
    monkeypatch.setattr(preparar.db, "session", lambda path: _NoConn())
    job = preparar.Job(user_id="u1")
    asyncio.run(preparar._work(preparar.Flow(NS(database_path=""), "r1", job, llm=object())))
    assert fake.generated == [["RN-004", "RN-005"]]
    # Rota no tenía lectura del código: se lee después de escribirla de nuevo
    assert fake.explained == ["RN-001", "RN-002", "RN-003", "RN-004", "RN-005"]
    assert fake.approved_tests == ["RN-001", "RN-002", "RN-005"]
    assert "2 escritas de nuevo rotas o que no coincidían (1 ya están bien)" in {s.id: s.note for s in job.steps}["revision"]


def test_quien_se_aprueba_solo():
    ok = lambda verdict, strength, cross, **kw: preparar.trusted_by_program(NS(test=NS(**{**vars(_test(verdict, strength)), **kw}), crosscheck=NS(status=cross)))
    assert ok("cumple", "fuerte", "coincide") and ok("no_cumple", None, "coincide")
    assert not ok("cumple", "parcial", "coincide") and not ok("cumple", "fuerte", "discrepa") and not ok("no_cumple", None, "discrepa")
    assert not ok("no_cumple", None, "sin_revisar") and not ok("prueba_rota", None, "coincide")
    assert not ok("no_cumple", None, "coincide", approved=True) and not ok("cumple", "fuerte", "coincide", blocked="Córrela primero")


def test_si_el_arnes_de_la_ia_no_arranca_se_corrige_y_se_prueba_otra_vez(monkeypatch):
    fake = Rutas()
    smokes = iter(["fallo", "paso"])
    state = {"smoke": "pendiente", "proposed": 0}
    fake.get_harness = lambda *a: NS(
        cloned=True, repo_harness=None, can_generate=True, sandbox=True,
        harness=NS(origin="ia", smoke=state["smoke"], approved=False, smoke_message="GET /citas respondió 401"),
    )
    fake.run_smoke = lambda *a: state.update(smoke=next(smokes))
    fake.approve_harness = lambda *a: None
    fake.create_harness = lambda *a: state.update(proposed=state["proposed"] + 1)
    for name in ("rule_routes", "harness_routes", "test_routes"):
        monkeypatch.setattr(preparar, name, fake)
    monkeypatch.setattr(preparar.db, "session", lambda path: _NoConn())
    job = preparar.Job(user_id="u1")
    asyncio.run(preparar._work(preparar.Flow(NS(database_path=""), "r1", job, llm=object())))
    nota = {s.id: (s.status, s.note) for s in job.steps}
    assert state["proposed"] == 1 and nota["humo"] == ("hecho", "El entorno arranca y se aprobó (la IA corrigió el entorno tras un primer intento que no arrancó)")
    assert job.summary == preparar.DONE
