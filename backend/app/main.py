from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.assistant.llm import model_label
from app.config import Settings, get_settings
from app.diagnostico import router as diagnostico
from app.errors import register_error_handlers

health_router = APIRouter(tags=["salud"])


@health_router.get("/api/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    """Estado de la API y de los servicios externos (la IA y el túnel público)."""
    llm = {"status": "ok", "label": "Configurado"} if settings.gemini_api_key else {"status": "standby", "label": "Sin configurar"}
    return {
        "status": "ok",
        "version": "0.1.0",
        "tunnel_host": None,
        "services": [
            {"id": "llm", "name": model_label(settings.gemini_model), "role": "Diagnóstico con IA", **llm},
            {"id": "tunnel", "name": "Cloudflare Tunnel", "role": "Acceso público", "status": "down", "label": "Inactivo"},
        ],
    }


def create_app() -> FastAPI:
    app = FastAPI(title="IA voy API", version="0.1.0")
    # En desarrollo el proxy de Vite sirve /api desde el mismo origen; CORS cubre el acceso directo
    app.add_middleware(CORSMiddleware, allow_origins=[get_settings().frontend_url], allow_methods=["*"], allow_headers=["*"])
    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(diagnostico.router)
    return app


app = create_app()
