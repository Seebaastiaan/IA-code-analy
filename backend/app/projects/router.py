"""Configuración del proyecto (docs/FRONTEND_SPEC.md §5.11 y §6.8). El id del proyecto es el del repo."""

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.analyses.access import Analyses, UserId, require_repo
from app.analyses.config_file import FILENAME, ConfigError, normalize, to_toml
from app.analyses.schemas import Thresholds, Weights
from app.analyses.store import ProjectConfig
from app.analyses.workspace import Workspace
from app.analysis.router import Config
from app.errors import ApiError

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["configuración"])


class ProjectConfigBody(BaseModel):
    weights: Weights
    thresholds: Thresholds
    ignored: list[str] = Field(default_factory=list, max_length=500)
    excluded: list[str] = Field(default_factory=list, max_length=500)


def to_body(cfg: ProjectConfig) -> ProjectConfigBody:
    return ProjectConfigBody(weights=Weights(**cfg.weights), thresholds=Thresholds(**cfg.thresholds), ignored=cfg.ignored, excluded=cfg.excluded)


@router.get("/{project_id}/config", response_model=ProjectConfigBody)
def get_config(project_id: str, store: Analyses, user_id: UserId) -> ProjectConfigBody:
    require_repo(store, user_id, project_id)
    return to_body(store.config(project_id))


@router.put("/{project_id}/config", response_model=ProjectConfigBody)
def save_config(project_id: str, body: ProjectConfigBody, store: Analyses, user_id: UserId, settings: Config) -> ProjectConfigBody:
    """Guarda la configuración; se aplica al instante en scores y hallazgos. También escribe `.ia_voy.toml` en el clon."""
    require_repo(store, user_id, project_id)
    try:
        cfg = normalize(ProjectConfig(weights=body.weights.model_dump(), thresholds=body.thresholds.model_dump(), ignored=body.ignored, excluded=body.excluded))
    except ConfigError as exc:
        raise ApiError(422, "invalid_config", str(exc)) from exc
    store.save_config(project_id, cfg)
    ws = Workspace(settings, project_id)
    if ws.exists():
        try:
            (ws.root / FILENAME).write_text(to_toml(cfg), encoding="utf-8")
        except OSError:
            # La configuración ya quedó guardada en la base de datos; el archivo es una copia
            log.warning("No se pudo escribir %s en el clon de %s", FILENAME, project_id, exc_info=True)
    return to_body(cfg)
