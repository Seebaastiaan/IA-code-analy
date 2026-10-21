from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import register_error_handlers

health_router = APIRouter(tags=["salud"])


@health_router.get("/api/health")
def health() -> dict:
    """Estado de la API. Los servicios (IA, túnel, sandbox) se agregan conforme se integran."""
    return {"status": "ok", "version": "0.1.0", "tunnel_host": None, "services": []}


def create_app() -> FastAPI:
    app = FastAPI(title="IA voy API", version="0.1.0")
    # En desarrollo el proxy de Vite sirve /api desde el mismo origen; CORS cubre el acceso directo
    app.add_middleware(CORSMiddleware, allow_origins=[get_settings().frontend_url], allow_methods=["*"], allow_headers=["*"])
    register_error_handlers(app)
    app.include_router(health_router)
    return app


app = create_app()
