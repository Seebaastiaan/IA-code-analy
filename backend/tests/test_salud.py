"""/api/health y el formato de errores que espera el frontend."""


def test_health_sin_sesion(anon):
    res = anon.get("/api/health")
    assert res.status_code == 200
    assert {s["id"] for s in res.json()["services"]} == {"llm", "tunnel"}


def test_health_muestra_el_modelo_sin_configurar(anon):
    [llm] = [s for s in anon.get("/api/health").json()["services"] if s["id"] == "llm"]
    assert llm["name"] == "Gemini 3.8 Flash" and llm["status"] == "standby"


def test_error_de_la_api_usa_el_formato_del_contrato(client):
    res = client.get("/api/report/no-existe-1")
    assert res.status_code == 404
    assert res.json() == {"error": {"code": "not_found", "message": "Reporte no encontrado"}}


def test_error_de_validacion_usa_el_formato_del_contrato(client):
    res = client.post("/api/analyze", json={"branch": "main"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "invalid_request" and "url" in res.json()["error"]["message"]
