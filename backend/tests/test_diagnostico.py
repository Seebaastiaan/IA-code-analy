"""Integración clonación ↔ IA: POST /api/diagnostico con git y Gemini sustituidos (sin red)."""

import pytest
from fastapi.testclient import TestClient

from app.assistant.llm import LlmError
from app.config import get_settings
from app.main import create_app

URL = "https://github.com/ana/api-pagos"


def diagnose(client, **body):
    return client.post("/api/diagnostico", json={"url": URL, **body})


def test_diagnostico_de_un_archivo(client, cloner):
    res = diagnose(client, file="app/core/servicio.py")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["repo"] == "ana/api-pagos" and body["commit"] == "abc1234" and body["file"] == "app/core/servicio.py"
    assert body["model"] == "Gemini 3.8 Flash"
    assert body["diagnostico"]["score"] == 72
    assert [h["regla"] for h in body["diagnostico"]["hallazgos"]] == ["HARDCODED-SECRET", "UNUSED-IMPORT"]
    # Se clona la URL normalizada, sin token (prototipo: solo repos públicos)
    assert cloner.calls == [{"url": URL, "branch": "main", "token": None}]


def test_sin_archivo_elige_el_primero_que_no_es_prueba(client):
    body = diagnose(client).json()
    assert body["file"] == "main.py"
    assert body["files"] == ["main.py", "app/__init__.py", "app/core/servicio.py", "tests/test_servicio.py"]


def test_el_prompt_lleva_reglas_y_codigo_numerado(client, llm):
    diagnose(client, file="app/core/servicio.py")
    call = llm.calls[-1]
    assert "RF-05" in call["system"] and "RN-09" in call["system"]
    prompt = call["turns"][0].text
    assert "ARCHIVO: app/core/servicio.py" in prompt
    assert '   3| CLAVE = "secreto123"' in prompt
    assert call["schema"]["required"] == ["resumen", "score", "hallazgos"]


def test_descarta_lineas_que_no_existen(client, llm):
    llm.reply["hallazgos"].append({"categoria": "prac", "severidad": "media", "linea": 999, "regla": "X", "mensaje": "inventado", "recomendacion": "-"})
    llm.reply["score"] = 140
    body = diagnose(client, file="app/core/servicio.py").json()
    assert all(h["linea"] <= 7 for h in body["diagnostico"]["hallazgos"])
    assert body["diagnostico"]["score"] == 100


def test_archivo_inexistente_o_fuera_del_clon(client):
    res = diagnose(client, file="no/existe.py")
    assert res.status_code == 404 and res.json()["error"]["code"] == "file_not_found"
    assert diagnose(client, file="../../secrets.json").status_code == 404


def test_repo_sin_python(client, cloner):
    cloner.files = {"index.js": "console.log(1)\n"}
    res = diagnose(client)
    assert res.status_code == 422 and res.json()["error"]["code"] == "no_python"


def test_fallo_al_clonar(client):
    res = diagnose(client, branch="no-existe")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "clone_failed" and "La rama no existe" in res.json()["error"]["message"]


@pytest.mark.parametrize("url", ["no-es-url", "https://gitlab.com/ana/repo", "https://10.0.0.1/ana/repo"])
def test_url_invalida(client, url):
    res = client.post("/api/diagnostico", json={"url": url})
    assert res.status_code == 422 and res.json()["error"]["code"] == "invalid_url"


def test_sin_clave_de_ia(settings, cloner):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings.model_copy(update={"gemini_api_key": ""})
    res = TestClient(app).post("/api/diagnostico", json={"url": URL})
    assert res.status_code == 503 and res.json()["error"]["code"] == "llm_not_configured"


def test_la_ia_no_responde(client, llm):
    llm.fail = LlmError("Gemini alcanzó su límite de solicitudes", kind="quota")
    res = diagnose(client)
    assert res.status_code == 503 and res.json()["error"]["code"] == "llm_unavailable"
