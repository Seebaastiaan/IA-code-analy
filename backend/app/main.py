from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import auth
from app.analysis import router as analysis
from app.assistant import router as assistant
from app.config import get_settings
from app.dashboard import router as dashboard
from app.editor import router as editor
from app.errors import register_error_handlers
from app.github import router as github
from app.projects import router as projects
from app.reports import router as reports
from app.share import router as share
from app.teams import router as teams


def create_app() -> FastAPI:
    app = FastAPI(title="IA voy API", version="0.8.0")
    # En desarrollo el proxy de Vite sirve /api desde el mismo origen; CORS cubre el acceso directo
    app.add_middleware(CORSMiddleware, allow_origins=[get_settings().frontend_url], allow_methods=["*"], allow_headers=["*"])
    register_error_handlers(app)
    app.include_router(auth.router)
    app.include_router(github.router)
    app.include_router(analysis.router)
    app.include_router(dashboard.router)
    app.include_router(reports.router)
    app.include_router(editor.router)
    app.include_router(assistant.router)
    app.include_router(projects.router)
    app.include_router(share.router)
    app.include_router(teams.router)
    return app


app = create_app()
