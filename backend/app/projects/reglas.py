"""
Configuración → Reglas de negocio (docs/PROPUESTA_REGLAS_NEGOCIO.md §2 y §6, ADR-003).

Las reglas son de cada proyecto (repo): la fuente oficial es su `reglas_negocio.toml`. Desde la app se pueden
cargar reglas de apoyo para ese proyecto (mientras se redactan): se validan igual —también contra las rutas de su
repositorio— y solo se usan en su análisis si el repo no tiene el archivo. No hay reglas generales.
"""

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from app.analyses import reglas
from app.analyses.access import Analyses, UserId, require_repo
from app.analyses.reglas_store import RulesStore
from app.analyses.workspace import Workspace
from app.analysis.router import Config
from app.errors import ApiError

router = APIRouter(tags=["reglas de negocio"])


class RulesContent(BaseModel):
    content: str = Field(max_length=reglas.MAX_BYTES)


class RulePreview(BaseModel):
    id: str
    title: str
    severity: str
    # Tiene `prohibido` u `obligatorio`; sin patrón la verifican sus pruebas
    pattern: bool


class Validation(BaseModel):
    valid: bool
    # Mensaje con la línea cuando se puede ("línea 14 · RN-02: …")
    error: str | None = None
    project: str | None = None
    rules: list[RulePreview] = Field(default_factory=list)
    # Revisadas contra el repositorio del proyecto: `rutas` que no existen en él (no bloquean el guardado)
    warnings: list[str] = Field(default_factory=list)


class RulesFile(Validation):
    content: str


class RepoRulesFile(RulesFile):
    # reglas_negocio.toml o docs/reglas_negocio.toml
    path: str


class UploadedRules(RulesFile):
    updated_at: str


class ProjectRules(BaseModel):
    # Qué reglas usa el siguiente análisis: las del repo, las cargadas en la app o ninguna
    active: Literal["repo", "app"] | None
    # None = el repo no tiene el archivo (o todavía no se clona: `cloned` = False)
    repo: RepoRulesFile | None
    uploaded: UploadedRules | None
    cloned: bool
    # Commit del último análisis (la versión del repo que se leyó)
    commit: str | None


def validate(text: str, files: list[str] | None = None, project: str = "") -> Validation:
    """`files` = archivos del clon del proyecto (None = sin clonar: las rutas no se revisan)."""
    try:
        rs = reglas.parse(text)
    except reglas.RulesError as exc:
        return Validation(valid=False, error=str(exc))
    return Validation(
        valid=True, project=rs.project,
        rules=[RulePreview(id=r.id, title=r.title, severity=r.severity, pattern=bool(r.forbidden or r.required)) for r in rs.rules],
        warnings=reglas.missing_paths(rs, files, project) if files is not None else [],
    )


def _files(ws: Workspace) -> list[str] | None:
    return ws.list_files([]) if ws.exists() else None


def _project_rules(store: Analyses, settings: Config, repo_id: str) -> ProjectRules:
    ws = Workspace(settings, repo_id)
    files = _files(ws)
    name = store.repo(repo_id)["name"]
    repo_file: RepoRulesFile | None = None
    if ws.exists():
        try:
            found = reglas.find(ws.root)
        except reglas.RulesError as exc:
            repo_file = RepoRulesFile(valid=False, error=str(exc), path=reglas.FILENAME, content="")
        else:
            if found:
                path, text = found
                repo_file = RepoRulesFile(**validate(text, files, name).model_dump(), path=path, content=text)
    row = RulesStore(store.conn).upload(repo_id)
    uploaded = UploadedRules(**validate(row["content"], files, name).model_dump(), content=row["content"], updated_at=row["updated_at"]) if row else None
    latest = store.latest_report(repo_id)
    return ProjectRules(
        active="repo" if repo_file else "app" if uploaded else None,
        repo=repo_file, uploaded=uploaded, cloned=ws.exists(), commit=latest["commit_sha"] if latest else None,
    )


@router.get("/api/projects/{project_id}/reglas", response_model=ProjectRules)
def get_rules(project_id: str, store: Analyses, user_id: UserId, settings: Config) -> ProjectRules:
    require_repo(store, user_id, project_id)
    return _project_rules(store, settings, project_id)


@router.put("/api/projects/{project_id}/reglas", response_model=ProjectRules)
def upload_rules(project_id: str, body: RulesContent, store: Analyses, user_id: UserId, settings: Config) -> ProjectRules:
    """Guarda reglas de apoyo en la app. Solo se aceptan válidas (`422 invalid_rules` con la línea del error)."""
    require_repo(store, user_id, project_id)
    result = validate(body.content)
    if not result.valid:
        raise ApiError(422, "invalid_rules", result.error or "Reglas no válidas")
    RulesStore(store.conn).save_upload(project_id, body.content, user_id)
    return _project_rules(store, settings, project_id)


@router.delete("/api/projects/{project_id}/reglas", response_model=ProjectRules)
def delete_rules(project_id: str, store: Analyses, user_id: UserId, settings: Config) -> ProjectRules:
    require_repo(store, user_id, project_id)
    RulesStore(store.conn).delete_upload(project_id)
    return _project_rules(store, settings, project_id)


@router.post("/api/projects/{project_id}/reglas/validar", response_model=Validation)
def validate_rules(project_id: str, body: RulesContent, store: Analyses, user_id: UserId, settings: Config) -> Validation:
    """Valida un reglas_negocio.toml del proyecto sin guardarlo (botón Validar): sintaxis y rutas de su repositorio."""
    repo = require_repo(store, user_id, project_id)
    return validate(body.content, _files(Workspace(settings, project_id)), repo["name"])


@router.get("/api/projects/{project_id}/reglas/plantilla")
def template(project_id: str, store: Analyses, user_id: UserId, settings: Config) -> Response:
    """Plantilla del proyecto: su nombre y rutas de carpetas que existen en su repositorio."""
    repo = require_repo(store, user_id, project_id)
    ws = Workspace(settings, project_id)
    return Response(
        reglas.template_for(repo["name"], ws.list_files([])), media_type="application/toml; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{reglas.FILENAME}"'},
    )
