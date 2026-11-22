"""
Reglas de negocio desde un documento de requisitos (POST /api/reglas/importar, docs/PLAN_IMPORTAR_REGLAS_DOCUMENTO.md)
con un modelo falso: sin red ni cuota de Gemini.
"""

import base64
import tomllib
import zipfile
from io import BytesIO

import pytest

from app.analyses import reglas
from app.analysis import clone as clone_mod
from app.analysis.clone import CloneResult
from app.assistant import router as assistant_router
from app.assistant.llm import Answer, LlmError
from app.config import Settings
from app.projects import reglas_importar as importar
from tests.conftest import FakeCloner
from tests.test_analysis import URL, wait_done

PDF = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n"
RN_LIMITE = {
    "titulo": "Un pago mayor al límite necesita autorización de admin o finanzas",
    "descripcion": "Un pago que pasa el límite del cliente solo se cobra si lo autorizó Administración o Finanzas.",
    "severidad": "alta",
    "criterio": "Dado un pago mayor al límite autorizado por «ventas», cuando se procesa, entonces se rechaza",
    "fuente": "pág. 4 · §3.2",
}
RN_DECIMAL = {"titulo": "Cobros exactos al centavo", "descripcion": "Lo cobrado coincide al centavo.", "severidad": "alta", "criterio": None, "fuente": "§3.1", "cita": "texto"}


class FakeLLM:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.reply: dict = {"reglas": [RN_LIMITE, RN_DECIMAL], "dudas": ["§5 habla de 'pagos grandes' pero no da el monto"]}
        self.fail: LlmError | None = None
        # Segunda pasada (solo contradicciones, sobre la lista final de reglas): se contesta aparte y no cuenta en `calls`
        self.second: list[dict] = []
        self.second_reply: dict = {"contradicciones": []}
        self.second_fail: LlmError | None = None

    def answer(self, system: str, turns: list, schema: dict, on_delta=None) -> Answer:
        if set(schema["properties"]) == {"contradicciones"}:
            self.second.append({"turns": turns})
            if self.second_fail:
                raise self.second_fail
            return Answer(self.second_reply, "Gemini 3.5 Flash Lite")
        self.calls.append({"system": system, "turns": turns, "schema": schema})
        if self.fail:
            raise self.fail
        return Answer(self.reply, "Gemini 3.5 Flash Lite")


@pytest.fixture
def llm(client) -> FakeLLM:
    fake = FakeLLM()
    client.app.dependency_overrides[assistant_router.get_llm] = lambda: fake
    return fake


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def docx(*paragraphs: str, extra: bytes = b"") -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = extra + f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>'.encode()
    out = BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("word/document.xml", xml)
    return out.getvalue()


def importar_archivo(client, filename: str, data: bytes, **extra):
    return client.post("/api/reglas/importar", json={"filename": filename, "data": b64(data), **extra})


# ─── Detección de documentos ───


def test_detecta_documentos_de_requisitos():
    blobs = {
        "README.md": 10, "docs/Requerimientos.pdf": 500, "Reglas de Negocio.docx": 300, "docs/arquitectura.md": 10,
        "tests/requerimientos.md": 10, "node_modules/x/requirements.md": 10, "CHANGELOG.md": 10,
        "historias_de_usuario.md": 0, "docs/SRS.pdf": importar.MAX_DOC_BYTES + 1, "docs/especificación.txt": 20, "requisitos.py": 5,
    }
    # docs/ primero; solo PDF y Word, sin vacíos, gigantes, pruebas, dependencias ni código
    assert importar.find_documents(blobs) == ["docs/Requerimientos.pdf", "Reglas de Negocio.docx"]


def test_solo_cuentan_pdf_y_word():
    blobs = {
        "requirements.txt": 50, "requirements-dev.txt": 20, "backend/requirements.txt": 30, "docs/requirements.md": 40,
        "docs/requisitos.txt": 10, "docs/requisitos.pdf": 40, "docs/reglas.docx": 40, "docs/reglas.doc": 40,
    }
    # La lista de paquetes de pip, el Markdown, el texto y el .doc antiguo no son documentos de requisitos
    assert importar.find_documents(blobs) == ["docs/reglas.docx", "docs/requisitos.pdf"]


def test_detecta_maximo_cinco():
    assert len(importar.find_documents({f"docs/requisitos_{i}.pdf": 1 for i in range(9)})) == importar.MAX_DOCUMENTS


# ─── TOML generado ───


def test_toml_generado_es_valido_y_numerado():
    content = importar.build_toml("ana/api-pagos", "docs/Requerimientos.pdf", [RN_LIMITE, RN_DECIMAL])
    rs = reglas.parse(content)
    assert [r.id for r in rs.rules] == ["RN-001", "RN-002"] and rs.project == "ana/api-pagos"
    assert rs.rules[0].criterion.startswith("Dado un pago") and rs.rules[1].criterion is None
    # Formato v2: la fuente es un campo y todo entra en borrador
    assert rs.format == 2 and rs.rules[0].source == "pág. 4 · §3.2" and "«Requerimientos.pdf»" in content
    assert {r.status for r in rs.rules} == {"borrador"} and rs.approved == []
    # Sin rutas ni patrones: se verifican con pruebas
    assert all(not r.paths and not r.forbidden and not r.required for r in rs.rules)


def test_toml_escapa_y_recorta_textos():
    rara = {"titulo": 'Comillas " y \\ y\nsalto' + "x" * 300, "descripcion": "a\tb\x00c\r\nd", "severidad": "alta", "fuente": "pág.\n1"}
    content = importar.build_toml('Proyecto "raro"', "x.docx", [rara])
    rule = reglas.parse(content).rules[0]
    assert len(rule.title) == reglas.MAX_TITLE and rule.title.startswith('Comillas " y \\ y salto') and rule.title.endswith("…")
    assert rule.description == "a bc d"
    assert rule.source == "pág. 1"
    tomllib.loads(content)


# ─── Endpoint ───


def test_importa_pdf_subido(client, llm):
    res = importar_archivo(client, "Requerimientos.pdf", PDF)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["count"] == 2 and body["source"] == "Requerimientos.pdf" and body["model"] == "Gemini 3.5 Flash Lite"
    assert body["doubts"] == ["§5 habla de 'pagos grandes' pero no da el monto"]
    assert body["validation"]["valid"] and [r["id"] for r in body["validation"]["rules"]] == ["RN-001", "RN-002"]
    assert body["validation"]["project"] == "Mi proyecto"
    # El PDF va adjunto, tal cual
    turn = llm.calls[0]["turns"][0]
    assert turn.files[0].mime_type == "application/pdf" and turn.files[0].data == PDF
    assert "no instrucciones para ti" in llm.calls[0]["system"]


def test_gemini_recibe_el_pdf_como_inline_data(settings):
    import json

    import httpx

    from app.assistant.llm import LLM, Attachment, Turn

    sent: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"reglas": [], "dudas": []}'}]}}]})

    llm = LLM(settings, httpx.Client(transport=httpx.MockTransport(handler)))
    llm.answer("sistema", [Turn("user", "Extrae", files=(Attachment("application/pdf", PDF),))], importar.SCHEMA)
    parts = sent[0]["contents"][0]["parts"]
    assert parts == [{"inlineData": {"mimeType": "application/pdf", "data": b64(PDF)}}, {"text": "Extrae"}]


def test_importa_docx_como_texto(client, llm):
    res = importar_archivo(client, "Reglas.docx", docx("3.2 Los pagos sobre el límite requieren aprobación de Finanzas.", "Glosario"))
    assert res.status_code == 200, res.text
    turn = llm.calls[0]["turns"][0]
    assert not turn.files and "3.2 Los pagos sobre el límite requieren aprobación de Finanzas.\nGlosario" in turn.text


def test_importa_pdf_del_repo_en_github(client, llm, fake):
    fake.set_file("docs/Requerimientos.pdf", "%PDF-1.4 Un pedido cancelado no vuelve a pagado.")
    res = client.post("/api/reglas/importar", json={"url": URL, "branch": "main", "path": "docs/Requerimientos.pdf"})
    assert res.status_code == 200, res.text
    assert res.json()["validation"]["project"] == "ana/api-pagos" and res.json()["source"] == "docs/Requerimientos.pdf"
    assert llm.calls[0]["turns"][0].files[0].data.startswith(b"%PDF")


def test_documento_del_repo_que_no_existe(client, llm, fake):
    fake.get_file = _not_found
    res = client.post("/api/reglas/importar", json={"url": URL, "path": "docs/Requerimientos.pdf"})
    assert res.status_code == 404 and res.json()["error"]["code"] == "not_found"
    assert not llm.calls


async def _not_found(*args, **kwargs):
    from app.github.client import GithubError

    raise GithubError(404, "Not Found")


def test_respuestas_raras_de_la_ia(client, llm):
    llm.reply = {"reglas": [{"titulo": "", "descripcion": "x", "severidad": "alta"}, {**RN_DECIMAL, "severidad": "CRÍTICA"}, "nada"], "dudas": [""]}
    body = importar_archivo(client, "r.docx", docx("texto")).json()
    assert body["count"] == 1 and body["doubts"] == []
    assert reglas.parse(body["content"]).rules[0].severity == "media"


def test_sin_reglas_responde_422_con_la_duda(client, llm):
    llm.reply = {"reglas": [], "dudas": ["El documento solo describe la arquitectura"]}
    res = importar_archivo(client, "arquitectura.docx", docx("Usamos FastAPI"))
    assert res.status_code == 422 and res.json()["error"]["code"] == "no_rules_found"
    assert "El documento solo describe la arquitectura" in res.json()["error"]["message"]


def test_maximo_de_reglas(client, llm):
    llm.reply = {"reglas": [{**RN_DECIMAL, "titulo": f"Regla {i}"} for i in range(reglas.MAX_RULES + 5)], "dudas": []}
    body = importar_archivo(client, "r.docx", docx("texto")).json()
    assert body["count"] == reglas.MAX_RULES and body["validation"]["valid"]
    assert body["doubts"][0].startswith(f"El documento tiene {reglas.MAX_RULES + 5} reglas")


def test_reglas_repetidas_dan_aviso(client, llm):
    llm.reply = {"reglas": [RN_DECIMAL, RN_DECIMAL], "dudas": []}
    body = importar_archivo(client, "r.docx", docx("texto")).json()
    assert body["validation"]["valid"] and body["validation"]["warnings"]


RN_24H = {"titulo": "Cancelar 24 h antes es gratis", "descripcion": "Con 24 h o más de anticipación se reembolsa todo.", "severidad": "alta", "fuente": "§4.2"}
RN_48H = {"titulo": "Cancelar con menos de 48 h cobra 50 %", "descripcion": "Toda cancelación con menos de 48 h cobra la mitad.", "severidad": "alta", "fuente": "§7.1"}
RN_PREMIUM = {"titulo": "Premium cancela gratis hasta 12 h antes", "descripcion": "Excepción para clientes premium.", "severidad": "media", "fuente": "§4.4"}


def test_contradicciones_se_marcan_y_bloquean_el_archivo(client, llm):
    llm.reply = {
        "reglas": [RN_24H, RN_PREMIUM, RN_48H],
        "contradicciones": [
            {"reglas": [1, 3], "motivo": "Entre 24 y 48 h una dice gratis y la otra cobra 50 %"},
            {"reglas": [3, 1], "motivo": "repetida al revés"}, {"reglas": [2, 2], "motivo": "consigo misma"},
            {"reglas": [1, 9], "motivo": "fuera de rango"}, {"reglas": [True, 3], "motivo": "no es un número"}, "nada",
        ],
        "dudas": [],
    }
    body = importar_archivo(client, "Requisitos.pdf", PDF).json()
    assert body["count"] == 3
    assert body["contradictions"] == ["RN-001 (§4.2) y RN-003 (§7.1): Entre 24 y 48 h una dice gratis y la otra cobra 50 %"]
    marca = "# CONTRADICCIÓN RN-001 RN-003: Entre 24 y 48 h una dice gratis y la otra cobra 50 %"
    # Junto a las dos reglas del par, y en ninguna otra
    assert body["content"].count(marca) == 2 and "# CONTRADICCIÓN RN-002" not in body["content"]
    assert f"{marca}\n[[regla]]\nid          = \"RN-001\"" in body["content"]
    # Mientras estén las dos, el archivo no se puede usar
    v = body["validation"]
    assert not v["valid"] and "RN-001 y RN-003 se contradicen según el documento" in v["error"] and "Deja solo la regla que vale" in v["error"]
    # El equipo deja la de 24 h: válido (la marca que queda ya no estorba)
    sin_48 = body["content"].split(f'\n\n{marca}\n[[regla]]\nid          = "RN-003"')[0] + "\n"
    assert reglas.parse(sin_48).rules[-1].id == "RN-002"
    # O decide que no se contradicen y borra los comentarios
    sin_marca = "\n".join(line for line in body["content"].splitlines() if not line.startswith("# CONTRADICCIÓN")) + "\n"
    assert len(reglas.parse(sin_marca).rules) == 3


def test_la_segunda_pasada_encuentra_lo_que_la_primera_no(client, llm):
    # La primera consulta no vio nada; la segunda recibe la lista final numerada por nosotros y marca el par 1-3
    llm.reply = {"reglas": [RN_24H, RN_PREMIUM, RN_48H], "contradicciones": [], "dudas": []}
    llm.second_reply = {"contradicciones": [{"reglas": [1, 3], "motivo": "24 h contra 48 h"}, {"reglas": [1, 7], "motivo": "fuera de rango"}]}
    body = importar_archivo(client, "Requisitos.pdf", PDF).json()
    assert body["contradictions"] == ["RN-001 (§4.2) y RN-003 (§7.1): 24 h contra 48 h"] and not body["validation"]["valid"]
    # Recibió las reglas ya numeradas, con su sección
    assert "1. §4.2" in llm.second[0]["turns"][0].text and "3. §7.1" in llm.second[0]["turns"][0].text
    # Si coincide con la primera no se repite
    llm.reply["contradicciones"] = [{"titulos": [RN_24H["titulo"], RN_48H["titulo"]], "motivo": "de la primera"}]
    assert importar_archivo(client, "Requisitos.pdf", PDF).json()["contradictions"] == ["RN-001 (§4.2) y RN-003 (§7.1): de la primera"]


def test_si_falla_la_segunda_pasada_la_importacion_sigue(client, llm):
    llm.reply = {"reglas": [RN_24H, RN_48H], "contradicciones": [], "dudas": []}
    llm.second_fail = LlmError("caído")
    body = importar_archivo(client, "Requisitos.pdf", PDF).json()
    assert body["count"] == 2 and body["contradictions"] == [] and body["validation"]["valid"]


def test_contradiccion_por_titulo_aunque_el_modelo_cuente_mal(client, llm):
    # Corrida real con Gemini: contó una regla de menos y marcó el par equivocado. Por título no importa cómo numere
    llm.reply = {
        "reglas": [RN_24H, RN_PREMIUM, RN_48H],
        "contradicciones": [
            {"titulos": [RN_24H["titulo"], RN_48H["titulo"].upper()], "motivo": "24 h contra 48 h"},
            {"titulos": [RN_24H["titulo"], "Una regla que no existe"], "motivo": "no está"}, {"titulos": [RN_24H["titulo"]], "motivo": "una sola"},
        ],
        "dudas": [],
    }
    body = importar_archivo(client, "Requisitos.pdf", PDF).json()
    assert body["contradictions"] == ["RN-001 (§4.2) y RN-003 (§7.1): 24 h contra 48 h"]


def test_contradiccion_apunta_bien_aunque_se_descarte_una_regla(client, llm):
    vacia = {"titulo": "", "descripcion": "", "severidad": "alta"}
    llm.reply = {"reglas": [vacia, RN_24H, RN_48H], "contradicciones": [{"reglas": [2, 3], "motivo": "24 h contra 48 h"}, {"reglas": [1, 2], "motivo": "con la vacía"}], "dudas": []}
    body = importar_archivo(client, "r.docx", docx("texto")).json()
    assert body["count"] == 2 and body["contradictions"] == ["RN-001 (§4.2) y RN-002 (§7.1): 24 h contra 48 h"]


def test_sin_contradicciones_en_la_respuesta(client, llm):
    # Respuesta sin la clave (modelo viejo o respuesta incompleta): sin contradicciones y archivo válido
    body = importar_archivo(client, "r.docx", docx("texto")).json()
    assert body["contradictions"] == [] and body["validation"]["valid"]


def test_el_prompt_pide_contradicciones_y_no_confundir_excepciones():
    assert "contradicciones" in importar.SCHEMA["required"]
    assert "NO es contradicción una" in importar.SYSTEM and "excepción" in importar.SYSTEM


def test_texto_largo_se_recorta_con_aviso(client, llm):
    body = importar_archivo(client, "r.docx", docx("a" * (importar.MAX_DOC_TEXT + 10))).json()
    assert body["doubts"][0].startswith("El documento es muy largo")
    assert len(llm.calls[0]["turns"][0].text) < importar.MAX_DOC_TEXT + 500


@pytest.mark.parametrize(
    ("filename", "data", "status", "code"),
    [
        ("virus.exe", b"MZ", 415, "unsupported_type"),
        ("falso.pdf", b"no soy pdf", 422, "invalid_document"),
        ("roto.docx", b"no soy zip", 422, "invalid_document"),
        ("vacio.docx", b"", 422, "invalid_document"),
        ("notas.md", b"# notas", 415, "unsupported_type"),
        ("datos.txt", b"texto", 415, "unsupported_type"),
        ("reglas.toml", b"[proyecto]", 415, "unsupported_type"),
        ("grande.pdf", b"%PDF" + b"0" * importar.MAX_DOC_BYTES, 413, "file_too_large"),
    ],
    ids=["exe", "pdf-falso", "docx-roto", "vacio", "markdown", "texto", "toml", "grande"],
)
def test_documentos_invalidos(client, llm, filename, data, status, code):
    res = importar_archivo(client, filename, data)
    assert res.status_code == status and res.json()["error"]["code"] == code
    assert not llm.calls


def test_docx_con_entidades_se_rechaza(client, llm):
    bomba = docx("x", extra=b'<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "aaaa">]>')
    res = importar_archivo(client, "bomba.docx", bomba)
    assert res.status_code == 422 and res.json()["error"]["code"] == "invalid_document"


def test_base64_invalido(client, llm):
    res = client.post("/api/reglas/importar", json={"filename": "r.docx", "data": "%%%no-base64"})
    assert res.status_code == 422 and res.json()["error"]["code"] == "invalid_document"


@pytest.mark.parametrize(("kind", "code"), [("quota", "llm_rate_limited"), ("busy", "llm_busy"), (None, "llm_unavailable")])
def test_errores_de_la_ia(client, llm, kind, code):
    llm.fail = LlmError("falló", kind=kind)
    res = importar_archivo(client, "r.docx", docx("texto"))
    assert res.status_code == 503 and res.json()["error"]["code"] == code


def test_sin_clave_de_gemini(client):
    res = importar_archivo(client, "r.docx", docx("texto"))
    assert res.status_code == 503 and res.json()["error"]["code"] == "llm_not_configured"


def test_requiere_sesion(anon):
    assert anon.post("/api/reglas/importar", json={"filename": "r.docx", "data": b64(b"x")}).status_code == 401


# ─── Revisión en Nuevo análisis y Configuración ───


def test_revisar_lista_documentos_y_si_hay_ia(client, fake, settings):
    fake.trees["ana/api-pagos"] += ["docs/Requerimientos.pdf", "README.md"]
    body = client.post("/api/reglas/revisar", json={"url": URL, "branch": "main"}).json()
    assert body["documents"] == ["docs/Requerimientos.pdf"] and body["can_import"] is False
    settings.gemini_api_key = "clave"
    assert client.post("/api/reglas/revisar", json={"url": URL, "branch": "main"}).json()["can_import"] is True


class ClonerConDocumento(FakeCloner):
    def clone(self, settings: Settings, repo_id: str, url: str, branch: str, token: str | None, attempt: str) -> CloneResult:
        result = super().clone(settings, repo_id, url, branch, token, attempt)
        tmp = clone_mod.clones_root(settings) / f"{repo_id}.tmp-{attempt}"
        (tmp / "docs").mkdir(exist_ok=True)
        (tmp / "docs" / "Requisitos.docx").write_bytes(docx("Todo pago mayor a $1,000 requiere autorización."))
        return result


@pytest.fixture
def cloner() -> ClonerConDocumento:
    return ClonerConDocumento()


def test_configuracion_importa_de_la_copia_del_proyecto(client, llm):
    rid = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"])["repo_id"]
    project = client.get(f"/api/projects/{rid}/reglas").json()
    assert project["documents"] == ["docs/Requisitos.docx"]
    res = client.post("/api/reglas/importar", json={"project_id": rid, "path": "docs/Requisitos.docx"})
    assert res.status_code == 200, res.text
    assert res.json()["validation"]["project"] == "ana/api-pagos"
    assert "Todo pago mayor a $1,000 requiere autorización." in llm.calls[0]["turns"][0].text
    # Fuera de la copia: rechazado
    assert client.post("/api/reglas/importar", json={"project_id": rid, "path": "../secreto.docx"}).json()["error"]["code"] == "invalid_path"
    # No guarda nada: el usuario lo revisa en el editor
    assert client.get(f"/api/projects/{rid}/reglas").json()["uploaded"] is None


def test_proyecto_de_otro_equipo(client, llm):
    res = client.post("/api/reglas/importar", json={"project_id": "no-existe", "path": "docs/Requisitos.docx"})
    assert res.status_code == 404


# ─── Cita textual verificada contra el documento ───

DOC_CITAS = "3.2 Los pagos mayores a $1,000 requieren la aprobación de Finanzas antes de procesarse."


def test_la_cita_se_busca_en_el_documento_aunque_cambien_acentos_y_signos():
    assert importar.quote_found(DOC_CITAS, "Los pagos mayores a $1,000 requieren la aprobacion de FINANZAS antes de procesarse")
    # Un par de palabras distintas todavía cuenta; una frase inventada no
    assert importar.quote_found(DOC_CITAS, "Los pagos mayores a $1,000 requieren la aprobación del área de Finanzas antes de procesarse")
    assert not importar.quote_found(DOC_CITAS, "Los clientes premium cancelan gratis hasta 12 horas antes del viaje")
    assert not importar.quote_found(DOC_CITAS, "corta")


def test_una_regla_sin_cita_valida_queda_con_duda(client, llm):
    ok = {**RN_DECIMAL, "cita": "Los pagos mayores a $1,000 requieren la aprobación de Finanzas"}
    inventada = {**RN_DECIMAL, "titulo": "Otra", "cita": "Todos los clientes reciben un regalo de bienvenida"}
    sin_cita = {**RN_DECIMAL, "titulo": "Sin cita", "cita": ""}
    llm.reply = {"reglas": [ok, inventada, sin_cita], "dudas": []}
    body = importar_archivo(client, "Reglas.docx", docx(DOC_CITAS)).json()
    rs = reglas.parse(body["content"])
    assert [r.quote_ok for r in rs.rules] == [True, False, False]
    assert rs.rules[0].quote == ok["cita"] and rs.rules[0].doubts == ()
    assert "No encontré la cita" in rs.rules[1].doubts[-1] and "no citó" in rs.rules[2].doubts[-1]


def test_en_un_pdf_ilegible_la_cita_no_se_puede_comprobar_y_no_se_inventa_una_duda(client, llm):
    llm.reply = {"reglas": [{**RN_DECIMAL, "cita": "Frase cualquiera del documento"}], "dudas": []}
    body = importar_archivo(client, "Reglas.pdf", b"%PDF-1.4 x").json()
    rule = reglas.parse(body["content"]).rules[0]
    assert rule.quote == "Frase cualquiera del documento" and rule.quote_ok is None and rule.doubts == ()
    assert "cita_verificada" not in body["content"]


def pdf_con_texto(*lines: str) -> bytes:
    """Un PDF mínimo con texto seleccionable (una línea por renglón), armado a mano."""
    content = "BT /F1 12 Tf 14 TL 50 700 Td " + " T* ".join(f"({line}) Tj" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for n, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def test_en_un_pdf_con_texto_la_cita_si_se_comprueba(client, llm):
    pdf = pdf_con_texto("3.2 Los pagos mayores a 1000 requieren la aprobacion de Finanzas antes de procesarse.")
    assert "aprobacion de Finanzas" in (importar.pdf_text(pdf) or "")
    ok = {**RN_DECIMAL, "cita": "Los pagos mayores a 1000 requieren la aprobacion de Finanzas"}
    inventada = {**RN_DECIMAL, "titulo": "Otra", "cita": "Todos los clientes reciben un regalo de bienvenida"}
    llm.reply = {"reglas": [ok, inventada], "dudas": []}
    rs = reglas.parse(importar_archivo(client, "Reglas.pdf", pdf).json()["content"])
    assert [r.quote_ok for r in rs.rules] == [True, False] and "No encontré la cita" in rs.rules[1].doubts[-1]


def test_un_pdf_sin_texto_o_roto_deja_la_cita_sin_comprobar():
    assert importar.pdf_text(b"%PDF-1.4 no es un pdf de verdad") is None
    assert importar.pdf_text(pdf_con_texto("corto")) is None


def test_las_frases_omitidas_se_avisan_solo_si_estan_en_el_documento(client, llm):
    llm.reply = {"reglas": [RN_DECIMAL], "omitidas": ["Los pagos mayores a $1,000 requieren la aprobación de Finanzas", "Frase que la IA se inventó por completo", ""], "dudas": []}
    body = importar_archivo(client, "Reglas.docx", docx(DOC_CITAS)).json()
    avisos = [d for d in body["doubts"] if d.startswith("Posible regla que no se extrajo")]
    assert avisos == ["Posible regla que no se extrajo: «Los pagos mayores a $1,000 requieren la aprobación de Finanzas»"]
