from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import auth
from app.analysis import router as analysis
from app.config import get_settings
from app.dashboard import router as dashboard
from app.errors import register_error_handlers
from app.reports import router as reports


def create_app() -> FastAPI:
    app = FastAPI(title="IA voy API", version="0.1.0")
    # En desarrollo el proxy de Vite sirve /api desde el mismo origen; CORS cubre el acceso directo
    app.add_middleware(CORSMiddleware, allow_origins=[get_settings().frontend_url], allow_methods=["*"], allow_headers=["*"])
    register_error_handlers(app)
    app.include_router(auth.router)
    app.include_router(analysis.router)
    app.include_router(dashboard.router)
    app.include_router(reports.router)
    return app


app = create_app()
