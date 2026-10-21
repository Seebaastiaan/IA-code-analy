"""API base: /api/health y el formato de errores que espera el frontend."""

from fastapi.testclient import TestClient

from app.errors import ApiError
from app.main import create_app


def test_health():
    res = TestClient(create_app()).get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_errores_usan_el_formato_del_contrato():
    app = create_app()

    @app.get("/api/falla")
    def falla() -> dict:
        raise ApiError(404, "not_found", "No existe")

    res = TestClient(app).get("/api/falla")
    assert res.status_code == 404
    assert res.json() == {"error": {"code": "not_found", "message": "No existe"}}
