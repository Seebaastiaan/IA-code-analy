"""
Archivos del último clon de un repositorio (solo lectura): árbol y contenido. La lista de repositorios y su
historial pasaron al tablero (app.dashboard) en el Sprint 6. docs/FRONTEND_SPEC.md §6.2.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.analyses.access import Analyses, UserId, require_repo
from app.analyses.workspace import Workspace, language_of
from app.config import Settings, get_settings
from app.errors import ApiError

router = APIRouter(prefix="/api", tags=["repositorios"])

Config = Annotated[Settings, Depends(get_settings)]


class TreeEntry(BaseModel):
    path: str
    dir: str


class FileResponse(BaseModel):
    path: str
    language: str
    content: str


def workspace(settings: Settings, repo_id: str) -> Workspace:
    ws = Workspace(settings, repo_id)
    if not ws.exists():
        raise ApiError(404, "not_cloned", "Este repositorio aún no se ha clonado. Vuelve a analizarlo.")
    return ws


@router.get("/repos/{repo_id}/tree", response_model=list[TreeEntry])
def tree(repo_id: str, store: Analyses, user_id: UserId, settings: Config) -> list[TreeEntry]:
    require_repo(store, user_id, repo_id)
    files = workspace(settings, repo_id).list_files(store.config(repo_id).excluded)
    entries = [TreeEntry(path=p, dir=p.rsplit("/", 1)[0] if "/" in p else "") for p in files]
    # Agrupado por carpeta (el árbol del frontend pinta un encabezado al cambiar de carpeta)
    return sorted(entries, key=lambda e: (e.dir, e.path))


@router.get("/file", response_model=FileResponse)
def read_file(store: Analyses, user_id: UserId, settings: Config, repo: str = Query(max_length=64), path: str = Query(max_length=500)) -> FileResponse:
    require_repo(store, user_id, repo)
    return FileResponse(path=path, language=language_of(path), content=workspace(settings, repo).read(path))
