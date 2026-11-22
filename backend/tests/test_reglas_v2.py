"""
Fase 1 de las reglas verificables (docs/PROPUESTA_REGLAS_VERIFICABLES.md §4, §5 y §14): formato v2 de
reglas_negocio.toml (tipo, estado, fuente, dudas y escenarios), importador v2 (reglas atómicas en borrador) y la tabla de
aprobación (solo las aprobadas se verifican; con dudas abiertas no se aprueba desde la app).
"""

from pathlib import Path

import pytest

from app.analyses import reglas
from app.assistant import router as assistant_router
from app.assistant.llm import Answer
from app.projects import reglas_concordancia as concordancia
from app.projects import reglas_importar as importar
from app.projects import reglas_pruebas as pruebas
from app.projects import reglas_respuestas as respuestas
from tests.test_analysis import URL, wait_done
from tests.test_reglas import correr, repo
from tests.test_reglas_importar import docx

SEED = Path(__file__).resolve().parent.parent / "seed_data"

V2 = '''# Reglas del inventario (comentario que no se pierde al editar)
[proyecto]
nombre  = "Inventario"
formato = 2

[[regla]]
id          = "RN-001"
titulo      = "El stock nunca es negativo"
descripcion = "No se vende más de lo que hay."
severidad   = "alta"
tipo        = "datos"
estado      = "aprobada"
fuente      = "Requerimientos.docx · §5.1"
dudas       = []

  [[regla.escenario]]
  dado     = "un producto con stock 3"
  cuando   = "se venden 5"
  entonces = "se rechaza y el stock sigue en 3"

# CONTRADICCIÓN-no: comentario normal entre reglas
[[regla]]
id          = "RN-002"
titulo      = "Precio de venta menor al costo"
descripcion = "Si precio < costo, el sistema lo bloquea."
severidad   = "media"
tipo        = "datos"
estado      = "borrador"
dudas       = [
  "«alerta/bloqueo»: ¿se avisa o se rechaza?",
  "¿Cuenta el precio con impuestos?",
]

[[regla]]
id          = "RN-003"
titulo      = "El gerente revisa las mermas cada semana"
descripcion = "Cada lunes el gerente firma el reporte de mermas."
severidad   = "baja"
tipo        = "proceso"
estado      = "aprobada"
'''


# ─── Formato v2 ───


def test_lee_los_campos_v2():
    rs = reglas.parse(V2)
    assert rs.format == 2 and rs.warnings == []
    r1, r2, r3 = rs.rules
    assert (r1.tipo, r1.status, r1.source, r1.doubts) == ("datos", "aprobada", "Requerimientos.docx · §5.1", ())
    assert r1.scenarios == (reglas.Scenario("un producto con stock 3", "se venden 5", "se rechaza y el stock sigue en 3"),)
    assert r2.status == "borrador" and len(r2.doubts) == 2 and r3.process
    assert [r.id for r in rs.approved] == ["RN-001", "RN-003"] and [r.id for r in rs.drafts] == ["RN-002"]


def test_un_archivo_v1_sigue_siendo_valido_y_su_criterio_es_un_escenario():
    for demo in ("inventario_demo", "reservas_demo"):
        rs = reglas.parse((SEED / demo / "referencia" / "reglas_negocio.toml").read_text(encoding="utf-8"))
        assert rs.format == 1 and rs.warnings == [] and all(r.approved and r.tipo is None for r in rs.rules)
    rs = reglas.parse((SEED / "inventario_demo" / "referencia" / "reglas_negocio.toml").read_text(encoding="utf-8"))
    rn1 = rs.rules[0]
    assert rn1.scenarios == (reglas.Scenario("un producto con una compra registrada", "el gerente lo elimina", "sigue existiendo con estado Inactivo y su Kardex intacto"),)
    # Un criterio que no es «Dado…, cuando…, entonces…» se queda como texto
    assert reglas.parse(reglas_v1(criterio='"Se rechaza siempre"')).rules[0].scenarios == ()
    # El hash de las pruebas generadas no cambia para las reglas v1 (no se desactualizan con el formato nuevo)
    import hashlib
    old = hashlib.sha256("\n".join([rn1.id, rn1.title, rn1.description, rn1.criterion or ""]).encode()).hexdigest()[:16]
    assert pruebas.rule_hash(rn1) == old


def reglas_v1(**campos: str) -> str:
    base = {"id": '"RN-001"', "titulo": '"T"', "descripcion": '"D"', "severidad": '"alta"', **campos}
    return '[proyecto]\nnombre = "P"\n\n[[regla]]\n' + "\n".join(f"{k} = {v}" for k, v in base.items()) + "\n"


@pytest.mark.parametrize(
    ("extra", "error"),
    [
        ('tipo = "magia"', "`tipo` debe ser datos, flujo"),
        ('estado = "lista"', "`estado` debe ser borrador o aprobada"),
        ("dudas = \"una\"", "`dudas` debe ser una lista de textos"),
        ("dudas = [1]", "`dudas` debe ser una lista de textos"),
        ('\n[[regla.escenario]]\ndado = "a"\ncuando = "b"', "escenario 1: falta `entonces`"),
        ('\n[[regla.escenario]]\ndado = "a"\ncuando = "b"\nentonces = "c"\nluego = "d"', "campo desconocido `luego`"),
        ('\n[regla.escenario]\ndado = "a"', "doble corchete"),
        ("".join('\n[[regla.escenario]]\ndado = "a"\ncuando = "b"\nentonces = "c"' for _ in range(11)), "máximo 10 escenarios"),
    ],
)
def test_errores_del_formato_v2(extra, error):
    with pytest.raises(reglas.RulesError, match=error):
        reglas.parse(reglas_v1() + extra + "\n")


def test_formato_desconocido():
    with pytest.raises(reglas.RulesError, match="`formato` debe ser 1 o 2"):
        reglas.parse('[proyecto]\nnombre = "P"\nformato = 3\n')


def test_avisos_de_campos_obsoletos_y_dudas_abiertas():
    rs = reglas.parse(reglas_v1(obligatorio="'x'", ia="true", dudas='["¿y si falta?"]'))
    assert [w.split(":")[0] for w in rs.warnings] == ["RN-001", "RN-001", "RN-001 está aprobada con 1 duda(s) abierta(s)"]
    assert "`obligatorio` está obsoleto" in rs.warnings[0] and "`ia` ya no se usa" in rs.warnings[1]


def test_la_plantilla_es_v2_y_no_da_avisos():
    rs = reglas.parse(reglas.TEMPLATE)
    assert rs.format == 2 and rs.warnings == [] and reglas.conflicts(rs.rules) == []
    assert {r.status for r in rs.rules} == {"aprobada", "borrador"} and any(r.scenarios for r in rs.rules)
    assert "obligatorio =" not in reglas.TEMPLATE


# ─── En el análisis ───


def test_solo_las_aprobadas_se_verifican_y_proceso_queda_fuera(tmp_path):
    root, files = repo(tmp_path, {"reglas_negocio.toml": V2, "app.py": "x = 1\n"})
    check = correr(root, files)
    # El borrador no sale en el reporte; la de proceso no se verifica
    assert [(r.rule.id, r.status) for r in check.results] == [("RN-001", "sin_verificar"), ("RN-003", "fuera_del_codigo")]
    assert any("1 regla(s) en borrador no se verifican" in w and "RN-002" in w for w in check.warnings)
    assert "fuera del código" in reglas.summary_line(check)
    # Una prueba del borrador no da el aviso de «regla que no está»
    root, files = repo(tmp_path / "b", {"reglas_negocio.toml": V2, "tests/test_x.py": "import pytest\n\n@pytest.mark.regla('RN-002')\ndef test_x():\n    pass\n"})
    assert not any("no está en" in w for w in correr(root, files).warnings)


# ─── Editar el texto desde la app ───


def test_aprobar_y_resolver_dudas_sin_tocar_lo_demas():
    text = reglas.set_fields(V2, "RN-002", {"estado": "aprobada", "dudas": []})
    rs = reglas.parse(text)
    assert rs.rules[1].status == "aprobada" and rs.rules[1].doubts == ()
    # El arreglo de varias líneas se reemplazó entero; el resto del archivo es igual
    assert "¿Cuenta el precio" not in text and "# Reglas del inventario" in text and "# CONTRADICCIÓN-no" in text
    assert [line for line in text.splitlines() if "RN-002" not in line and "estado" not in line and "dudas" not in line and "«alerta" not in line and "¿Cuenta" not in line and line.strip() != "]"] == [
        line for line in V2.splitlines() if "RN-002" not in line and "estado" not in line and "dudas" not in line and "«alerta" not in line and "¿Cuenta" not in line and line.strip() != "]"
    ]
    assert rs.rules[0] == reglas.parse(V2).rules[0] and rs.rules[2] == reglas.parse(V2).rules[2]


def test_agregar_un_campo_que_no_estaba():
    text = reglas.set_fields(reglas_v1(), "RN-001", {"estado": "borrador"})
    assert reglas.parse(text).rules[0].status == "borrador"
    # Si la última clave es la que se cambia, lo nuevo no se pierde
    text = reglas.set_fields(reglas_v1(dudas='["a"]'), "RN-001", {"dudas": None, "estado": "borrador"})
    rule = reglas.parse(text).rules[0]
    assert rule.status == "borrador" and rule.doubts == ()
    # La clave de un escenario no se confunde con la de la regla
    con_escenario = reglas.set_fields(V2, "RN-001", {"estado": "borrador"})
    assert reglas.parse(con_escenario).rules[0].scenarios == reglas.parse(V2).rules[0].scenarios


def test_editar_una_regla_que_no_esta():
    with pytest.raises(reglas.RulesError, match="RN-009 no está"):
        reglas.set_fields(V2, "RN-009", {"estado": "aprobada"})


# ─── Importador v2 ───


RESPUESTA = {
    "reglas": [
        {"titulo": "El SKU no se repite", "descripcion": "Dos productos no tienen el mismo SKU.", "severidad": "alta", "tipo": "datos", "fuente": "§4.2", "cita": "SKU y nombre únicos",
         "escenarios": [{"dado": "un producto con SKU CAF-001", "cuando": "se da de alta otro con CAF-001", "entonces": "se rechaza y queda uno solo"}], "dudas": []},
        {"titulo": "El nombre interno no se repite", "descripcion": "Dos productos no tienen el mismo nombre.", "severidad": "media", "tipo": "datos", "fuente": "§4.2", "cita": "SKU y nombre únicos",
         "escenarios": [{"dado": "«Café molido»", "cuando": "se da de alta «café  Molido»", "entonces": "se rechaza"}],
         "dudas": ["¿Se comparan sin mayúsculas ni espacios repetidos?", "  "]},
        {"titulo": "El gerente firma las mermas cada lunes", "descripcion": "Revisión semanal.", "severidad": "baja", "tipo": "proceso", "fuente": "§9.2", "cita": "SKU y nombre únicos",
         "escenarios": [{"dado": "x", "cuando": "y", "entonces": "z"}], "dudas": []},
        {"titulo": "Sin tipo válido", "descripcion": "D", "severidad": "rara", "tipo": "magia", "fuente": "", "cita": "SKU y nombre únicos", "escenarios": [{"dado": "", "cuando": "b", "entonces": "c"}], "dudas": []},
    ],
    "contradicciones": [],
    "dudas": ["El documento no trae la sección 6"],
}


class FakeLLM:
    def __init__(self, reply: dict) -> None:
        self.reply = reply
        self.calls: list = []

    def answer(self, system, turns, schema, on_delta=None) -> Answer:
        self.calls.append((system, schema))
        return Answer(self.reply, "Gemini 3.5 Flash Lite")


def test_el_importador_v2_arma_reglas_atomicas_en_borrador():
    llm = FakeLLM(RESPUESTA)
    out = importar.extract(llm, "Inventario", "Requerimientos.docx", docx("SKU y nombre únicos."))
    rs = reglas.parse(out.content)
    assert out.count == 4 and rs.format == 2 and {r.status for r in rs.rules} == {"borrador"}
    sku, nombre, firma, rara = rs.rules
    assert (sku.tipo, sku.source, len(sku.scenarios), sku.doubts) == ("datos", "§4.2", 1, ())
    assert nombre.doubts == ("¿Se comparan sin mayúsculas ni espacios repetidos?",)
    # La de proceso no lleva escenarios (no hay prueba); un tipo o un escenario inválido se quita
    assert firma.process and firma.scenarios == ()
    assert (rara.tipo, rara.severity, rara.scenarios) == (None, "media", ())
    # Las dudas de cada regla, con su id y su fuente, antes que las del documento
    assert out.doubts == ["RN-002 (§4.2): ¿Se comparan sin mayúsculas ni espacios repetidos?", "El documento no trae la sección 6"]
    system, schema = llm.calls[0]
    assert "Separa SIEMPRE las reglas compuestas" in system and '"proceso"' in system
    assert {"tipo", "escenarios", "dudas"} <= set(schema["properties"]["reglas"]["items"]["required"])


def test_una_respuesta_sin_escenarios_conserva_el_criterio():
    viejo = {"reglas": [{"titulo": "T", "descripcion": "D", "severidad": "alta", "criterio": "Dado a, cuando b, entonces c", "fuente": "§1"}], "dudas": []}
    rule = reglas.parse(importar.extract(FakeLLM(viejo), "P", "r.docx", docx("x")).content).rules[0]
    assert rule.criterion == "Dado a, cuando b, entonces c" and rule.scenarios == (reglas.Scenario("a", "b", "c"),)


# ─── Tabla de aprobación (API) ───


@pytest.fixture
def rid(client) -> str:
    return wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])["repo_id"]


def test_aprobar_desde_la_app(client, rid):
    assert client.put(f"/api/projects/{rid}/reglas", json={"content": V2}).status_code == 200
    rules = {r["id"]: r for r in client.get(f"/api/projects/{rid}/reglas").json()["uploaded"]["rules"]}
    assert rules["RN-002"]["status"] == "borrador" and len(rules["RN-002"]["doubts"]) == 2 and rules["RN-001"]["scenarios"][0]["when"] == "se venden 5"
    assert rules["RN-001"]["tipo"] == "datos" and rules["RN-001"]["source"] == "Requerimientos.docx · §5.1"

    # Con dudas abiertas no se aprueba: se dice por qué
    body = client.post(f"/api/projects/{rid}/reglas/estado", json={"ids": ["RN-002"], "status": "aprobada"}).json()
    assert body["messages"] == ["RN-002: tiene 2 duda(s) abierta(s); resuélvelas antes de aprobarla"]
    assert {r["id"]: r["status"] for r in body["uploaded"]["rules"]}["RN-002"] == "borrador"

    # Se resuelven (una a una) y entonces sí
    doubts = rules["RN-002"]["doubts"]
    client.put(f"/api/projects/{rid}/reglas/RN-002/dudas", json={"doubts": doubts[1:]})
    body = client.put(f"/api/projects/{rid}/reglas/RN-002/dudas", json={"doubts": []}).json()
    assert {r["id"]: r["doubts"] for r in body["uploaded"]["rules"]}["RN-002"] == []
    body = client.post(f"/api/projects/{rid}/reglas/estado", json={"ids": ["RN-002"], "status": "aprobada"}).json()
    assert body["messages"] == [] and {r["id"]: r["status"] for r in body["uploaded"]["rules"]}["RN-002"] == "aprobada"
    # El comentario del archivo sigue ahí
    assert "# Reglas del inventario" in body["uploaded"]["content"]

    # Volver a borrador
    body = client.post(f"/api/projects/{rid}/reglas/estado", json={"ids": ["RN-001", "RN-003"], "status": "borrador"}).json()
    assert [r["status"] for r in body["uploaded"]["rules"]] == ["borrador", "aprobada", "borrador"]
    res = client.post(f"/api/projects/{rid}/reglas/estado", json={"ids": ["RN-404"], "status": "aprobada"})
    assert res.status_code == 404 and res.json()["error"]["code"] == "unknown_rule"


def test_contestar_una_duda_con_si_o_no_queda_en_la_regla_y_se_recuerda(client, rid):
    assert client.put(f"/api/projects/{rid}/reglas", json={"content": V2}).status_code == 200
    doubt = "¿Cuenta el precio con impuestos?"
    body = client.post(f"/api/projects/{rid}/reglas/RN-002/respuesta", json={"doubt": doubt, "answer": "no"}).json()
    rule = {r["id"]: r for r in body["uploaded"]["rules"]}["RN-002"]
    assert rule["doubts"] == ["«alerta/bloqueo»: ¿se avisa o se rechaza?"]
    assert rule["description"].endswith(f"Aclaración del equipo: {doubt} No.")
    # Una duda que ya no está abierta no se contesta dos veces
    assert client.post(f"/api/projects/{rid}/reglas/RN-002/respuesta", json={"doubt": doubt, "answer": "si"}).status_code == 409
    assert client.post(f"/api/projects/{rid}/reglas/RN-099/respuesta", json={"doubt": doubt, "answer": "si"}).status_code == 404
    assert client.post(f"/api/projects/{rid}/reglas/RN-002/respuesta", json={"doubt": doubt, "answer": "tal vez"}).status_code == 422

    # Una importación nueva con la misma pregunta (aunque la redacte distinto) se contesta sola
    again = V2.replace(doubt, "¿Cuenta el precio con impuestos incluidos?").replace("RN-002", "RN-007")
    body = client.put(f"/api/projects/{rid}/reglas", json={"content": again}).json()
    rule = {r["id"]: r for r in body["uploaded"]["rules"]}["RN-007"]
    assert rule["doubts"] == ["«alerta/bloqueo»: ¿se avisa o se rechaza?"] and "Aclaración del equipo" in rule["description"]
    assert body["messages"] == ["RN-007: ya respondiste «¿Cuenta el precio con impuestos incluidos?»: No"]


def test_la_respuesta_recordada_no_se_aplica_a_otra_regla():
    memory = [{"title": "Precio de venta menor al costo", "question": "¿Cuenta el precio con impuestos?", "answer": "si"}]
    text, messages = respuestas.apply(V2.replace("Precio de venta menor al costo", "El gerente aprueba descuentos"), memory)
    assert messages == [] and text.count("¿Cuenta el precio con impuestos?") == 1
    assert respuestas.apply(V2, [])[1] == []


def test_la_aclaracion_no_pasa_del_largo_permitido():
    long = "x" * (reglas.MAX_TEXT - 20)
    out = respuestas.with_note(long, "¿Una pregunta bastante larga que no cabe?", "si")
    assert len(out) <= reglas.MAX_TEXT
    assert respuestas.with_note("x" * reglas.MAX_TEXT, "¿Cabe?", "si") == "x" * reglas.MAX_TEXT


def test_sin_reglas_en_la_app_no_hay_nada_que_aprobar(client, rid):
    res = client.post(f"/api/projects/{rid}/reglas/estado", json={"ids": ["RN-001"], "status": "aprobada"})
    assert res.status_code == 409 and res.json()["error"]["code"] == "no_rules"


def test_las_del_repo_se_aprueban_en_su_copia_de_trabajo(client, settings, rid):
    from app.analysis.clone import clone_dir

    # El repo trae su reglas_negocio.toml válido: manda sobre lo de la app. Se edita la copia de trabajo (con respaldo,
    # como el editor); GitHub no se toca, y la respuesta lo dice
    archivo = clone_dir(settings, rid) / reglas.FILENAME
    archivo.write_text(V2, encoding="utf-8")
    assert client.get(f"/api/projects/{rid}/reglas").json()["active"] == "repo"

    # RN-001 viene aprobada: se vuelve a borrador y luego se aprueba junto con RN-002 (que tiene dudas)
    body = client.post(f"/api/projects/{rid}/reglas/estado", json={"ids": ["RN-001"], "status": "borrador"}).json()
    assert {r["id"]: r["status"] for r in body["repo"]["rules"]}["RN-001"] == "borrador" and body["messages"][-1].startswith("Guardado en la copia del proyecto")
    body = client.post(f"/api/projects/{rid}/reglas/estado", json={"ids": ["RN-001", "RN-002"], "status": "aprobada"}).json()
    assert body["messages"][0].startswith("RN-002: tiene 2 duda(s)") and body["messages"][-1].startswith("Guardado en la copia del proyecto")
    estados = {r["id"]: r["status"] for r in body["repo"]["rules"]}
    assert estados["RN-001"] == "aprobada" and estados["RN-002"] == "borrador"
    assert "# Reglas del inventario" in archivo.read_text(encoding="utf-8")
    # Respaldo de la versión anterior, junto a la base (data/backups/{repo}/{fecha}/{ruta})
    backups = list((Path(settings.database_path).parent / "backups" / rid).rglob(reglas.FILENAME))
    assert len(backups) == 2 and any(b.read_text(encoding="utf-8") == V2 for b in backups)

    # Las dudas también; sin cambios no hay aviso de la copia
    body = client.put(f"/api/projects/{rid}/reglas/RN-002/dudas", json={"doubts": []}).json()
    assert {r["id"]: r["doubts"] for r in body["repo"]["rules"]}["RN-002"] == [] and body["messages"][0].startswith("Guardado en la copia")
    body = client.post(f"/api/projects/{rid}/reglas/estado", json={"ids": ["RN-001"], "status": "aprobada"}).json()
    assert body["messages"] == []
    # Lo guardado en la app no se toca
    assert body["uploaded"] is None


def test_el_archivo_del_repo_con_errores_no_se_edita(client, settings, rid):
    from app.analysis.clone import clone_dir

    (clone_dir(settings, rid) / reglas.FILENAME).write_text(V2.replace('severidad   = "alta"', 'severidad   = "urgente"', 1), encoding="utf-8")
    res = client.post(f"/api/projects/{rid}/reglas/estado", json={"ids": ["RN-001"], "status": "aprobada"})
    assert res.status_code == 409 and res.json()["error"]["code"] == "invalid_repo_rules" and "corrígelo primero" in res.json()["error"]["message"]


def test_las_pruebas_generadas_son_solo_de_las_aprobadas(client, rid, settings):
    client.put(f"/api/projects/{rid}/reglas", json={"content": V2})
    from app.db import session

    with session(settings.database_path) as conn:
        ctx = pruebas.context(conn, settings, rid)
    assert [r.id for r in ctx.rules] == ["RN-001", "RN-003"]


def test_una_regla_de_proceso_no_llama_a_la_ia(client):
    rule = reglas.parse(V2).rules[2]
    llm = FakeLLM({})
    g = pruebas.generate(llm, Path("."), None, "", rule)
    assert (g.kind, llm.calls) == ("fuera_del_codigo", [])


def test_escenarios_y_tipo_van_a_la_ia():
    text = pruebas._rule_text(reglas.parse(V2).rules[0])
    assert "tipo: datos" in text and "dado un producto con stock 3 · cuando se venden 5 · entonces se rechaza y el stock sigue en 3" in text


def test_lo_que_aprueba_el_programa_se_marca_y_se_revierte(client, rid):
    assert client.put(f"/api/projects/{rid}/reglas", json={"content": V2.replace('estado      = "aprobada"\nfuente', 'estado      = "borrador"\nfuente', 1)}).status_code == 200
    body = client.post(f"/api/projects/{rid}/reglas/estado", json={"ids": ["RN-001"], "status": "aprobada", "by": "programa"}).json()
    rule = {r["id"]: r for r in body["uploaded"]["rules"]}["RN-001"]
    assert (rule["status"], rule["approved_by"]) == ("aprobada", "programa") and 'aprobada_por = "programa"' in body["uploaded"]["content"]
    # Revertir en un clic: vuelve a borrador y la marca desaparece
    body = client.post(f"/api/projects/{rid}/reglas/estado", json={"ids": ["RN-001"], "status": "borrador"}).json()
    rule = {r["id"]: r for r in body["uploaded"]["rules"]}["RN-001"]
    assert (rule["status"], rule["approved_by"]) == ("borrador", None) and "aprobada_por" not in body["uploaded"]["content"]
    # Aprobada por el equipo: sin marca
    body = client.post(f"/api/projects/{rid}/reglas/estado", json={"ids": ["RN-001"], "status": "aprobada"}).json()
    assert {r["id"]: r for r in body["uploaded"]["rules"]}["RN-001"]["approved_by"] is None


def test_el_documento_manda_la_ia_corrige_el_codigo_no_la_regla(client, rid, settings):
    from app import db
    from app.analyses.reglas_store import RulesStore
    from app.analysis.clone import clone_dir
    from tests.test_reglas import REGLAS
    from tests.test_reglas import repo as write_repo

    settings.gemini_api_key = "clave"
    # El código del repo de prueba y sus reglas, y el resultado del análisis (RN-001 no se cumple: usa float)
    root = clone_dir(settings, rid)
    files = write_repo(root, {"reglas_negocio.toml": REGLAS, "app/pagos/cobro.py": "def cobrar(m):\n    return float(m)\n"})[1]
    with db.session(settings.database_path) as conn:
        report = conn.execute("SELECT id FROM reports WHERE repo_id = ? ORDER BY num DESC LIMIT 1", (rid,)).fetchone()["id"]
        RulesStore(conn).save(report, reglas.run(root, files, lambda f: (root / f).read_text(encoding="utf-8").split("\n")))
    llm = FakeLLM({"edits": [{"start_line": 2, "end_line": 2, "replacement": "    return Decimal(str(m))"}], "imports": ["from decimal import Decimal"], "explanation": "Usé Decimal para no perder centavos."})
    client.app.dependency_overrides[assistant_router.get_llm] = lambda: llm
    try:
        # RN-001 («float» prohibido en app/pagos/) no se cumple en el repo de prueba
        res = client.post(f"/api/projects/{rid}/reglas/pruebas/RN-001/corregir")
        assert res.status_code == 200, res.json()
        body = res.json()
        assert body["places"] == ["app/pagos/cobro.py:2"] and "Decimal" in "".join(p["text"] or "" for p in body["patches"])
        assert {p["file"] for p in body["patches"]} == {"app/pagos/cobro.py"} and body["notes"] == ["app/pagos/cobro.py: Usé Decimal para no perder centavos."]
        # Una regla que no está incumplida no se corrige; una que no existe, tampoco
        assert client.post(f"/api/projects/{rid}/reglas/pruebas/RN-002/corregir").json()["error"]["code"] == "not_violated"
        assert client.post(f"/api/projects/{rid}/reglas/pruebas/RN-099/corregir").status_code == 404
    finally:
        client.app.dependency_overrides.pop(assistant_router.get_llm, None)


def test_el_programa_acierta_si_coincide_con_lo_que_el_equipo_sabe():
    out = concordancia.outcome
    assert (out("cumple", "cumple"), out("viola", "no_cumple"), out("viola", "no_implementada")) == ("acerto", "acerto", "acerto")
    assert (out("cumple", "no_cumple"), out("viola", "cumple")) == ("fallo", "fallo")
    assert (out("cumple", "sin_verificar"), out("viola", "prueba_rota"), out("cumple", None)) == ("sin_resultado",) * 3
    assert out(None, "cumple") is None
    items = concordancia.build([("RN-001", "A"), ("RN-002", "B")], {"RN-001": "cumple"}, {"RN-001": ("cumple", "pruebas_y_patron")})
    assert [(i.outcome, i.confidence) for i in items] == [("acerto", "alta"), (None, None)]


def test_casos_de_control_y_panel_de_concordancia(client, rid):
    assert client.put(f"/api/projects/{rid}/reglas", json={"content": V2}).status_code == 200
    body = client.get(f"/api/projects/{rid}/reglas/concordancia").json()
    assert [i["rule_id"] for i in body["items"]] == ["RN-001", "RN-002", "RN-003"] and body["known"] == 0

    body = client.put(f"/api/projects/{rid}/reglas/RN-001/esperado", json={"expected": "cumple"}).json()
    item = body["items"][0]
    # El análisis no tiene resultado para ella todavía: no se cuenta ni como acierto ni como fallo
    assert (item["expected"], item["outcome"]) == ("cumple", "sin_resultado")
    assert (body["known"], body["hits"], body["misses"], body["unverified"]) == (1, 0, 0, 1)

    body = client.put(f"/api/projects/{rid}/reglas/RN-001/esperado", json={"expected": None}).json()
    assert body["known"] == 0 and body["items"][0]["expected"] is None
    assert client.put(f"/api/projects/{rid}/reglas/RN-099/esperado", json={"expected": "viola"}).status_code == 404
    assert client.put(f"/api/projects/{rid}/reglas/RN-001/esperado", json={"expected": "quizá"}).status_code == 422


def test_escribir_una_regla_con_palabras_normales_la_agrega_en_borrador(client, rid):
    reply = {
        "titulo": "Un descuento mayor al 20% necesita al gerente", "descripcion": "Solo el gerente aprueba descuentos de más del 20%.", "severidad": "alta",
        "tipo": "permisos", "escenarios": [{"dado": "un vendedor", "cuando": "aplica 25%", "entonces": "se rechaza"}], "dudas": ["¿El 20% exacto necesita al gerente?"],
    }
    llm = FakeLLM(reply)
    client.app.dependency_overrides[assistant_router.get_llm] = lambda: llm
    try:
        # Sin reglas todavía: arma el archivo con ella
        body = client.post(f"/api/projects/{rid}/reglas/redactar", json={"text": "Los descuentos de más del 20% los aprueba el gerente"}).json()
        assert body["messages"] == ["RN-001 agregada en borrador: revísala y apruébala"]
        # Con reglas: sigue la numeración y no toca lo demás
        assert client.put(f"/api/projects/{rid}/reglas", json={"content": V2}).status_code == 200
        body = client.post(f"/api/projects/{rid}/reglas/redactar", json={"text": "Otra regla"}).json()
        rules = {r["id"]: r for r in body["uploaded"]["rules"]}
        assert list(rules) == ["RN-001", "RN-002", "RN-003", "RN-004"]
        assert rules["RN-004"]["status"] == "borrador" and rules["RN-004"]["doubts"] == ["¿El 20% exacto necesita al gerente?"]
        assert rules["RN-004"]["source"] == "Escrita por el equipo" and "# Reglas del inventario" in body["uploaded"]["content"]
        assert client.post(f"/api/projects/{rid}/reglas/redactar", json={"text": "   "}).status_code == 422
    finally:
        client.app.dependency_overrides.pop(assistant_router.get_llm, None)


def test_get_llm_override_no_queda(client):
    # Las pruebas de arriba no dejan un modelo falso puesto para las demás
    assert assistant_router.get_llm not in client.app.dependency_overrides


# ─── Documento para leer y presentar ───

TOML_DOC = """[proyecto]
nombre  = "Tienda"
formato = 2

[[regla]]
id          = "RN-001"
titulo      = "El stock nunca es negativo"
descripcion = "El stock nunca es negativo"
severidad   = "alta"
tipo        = "datos"
estado      = "aprobada"
fuente      = "Cap. 2 «Inventario» · pág. 4"

  [[regla.escenario]]
  dado     = "un producto con stock 3"
  cuando   = "se venden 5"
  entonces = "se rechaza y el stock sigue en 3"

[[regla]]
id          = "RN-002"
titulo      = "Reporte semanal"
descripcion = "El gerente <revisa> el reporte cada lunes."
severidad   = "baja"
tipo        = "proceso"
estado      = "borrador"
dudas       = ["¿A qué hora?"]
"""


def test_el_documento_de_reglas_se_lee_sin_toml():
    from app.projects import reglas_documento as documento

    rs = reglas.parse(TOML_DOC)
    md = documento.markdown(rs)
    assert "# Reglas de negocio · Tienda" in md and "2 reglas: 1 aprobadas y 1 en borrador." in md
    assert "**Dado** un producto con stock 3; **cuando** se venden 5; **entonces** se rechaza y el stock sigue en 3." in md
    # La descripción igual al título no se repite; las dudas y la fuente sí salen
    assert md.count("El stock nunca es negativo") == 2 and "- ¿A qué hora?" in md and "Cap. 2 «Inventario» · pág. 4" in md
    assert "Fuera del código" in md
    page = documento.html(rs)
    assert page.startswith("<!doctype html>") and "&lt;revisa&gt;" in page and "<revisa>" not in page


def test_el_api_entrega_el_documento_en_html_y_markdown(client):
    rid = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])["repo_id"]
    assert client.get(f"/api/projects/{rid}/reglas/documento").json()["error"]["code"] == "no_rules"
    assert client.put(f"/api/projects/{rid}/reglas", json={"content": TOML_DOC}).status_code == 200
    res = client.get(f"/api/projects/{rid}/reglas/documento")
    assert res.status_code == 200 and "text/html" in res.headers["content-type"] and "reglas_de_negocio.html" in res.headers["content-disposition"]
    assert "Reglas de negocio · Tienda" in res.text
    md = client.get(f"/api/projects/{rid}/reglas/documento", params={"formato": "md"})
    assert "text/markdown" in md.headers["content-type"] and md.text.startswith("# Reglas de negocio · Tienda")
