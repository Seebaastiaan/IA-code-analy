"""
Configuración → Reglas de negocio (docs/PROPUESTA_REGLAS_NEGOCIO.md §2 y §6, ADR-003).

Las reglas son de cada proyecto (repo): la fuente oficial es su `reglas_negocio.toml`. Desde la app se pueden
cargar reglas de apoyo para ese proyecto (mientras se redactan, o para corregir un archivo del repo con errores): se
validan igual —también contra las rutas de su repositorio— y se usan en su análisis si el repo no tiene el archivo o
el suyo no es válido. No hay reglas generales.

`POST /api/reglas/revisar` revisa las reglas al cargar el repo (Nuevo análisis), antes de clonar: lee el archivo
con la API de GitHub y lo valida con el mismo parser.
"""

from collections.abc import Awaitable, Callable
from typing import Literal

import httpx
from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from app.analyses import reglas
from app.analyses.access import Analyses, UserId, require_repo
from app.analyses.reglas_store import RulesStore
from app.analyses.workspace import Workspace
from app.analysis.router import BRANCH, REPO_URL, Config, Db
from app.errors import ApiError
from app.github.client import GithubAuthError, GithubError
from app.github.deps import Client, Store
from app.teams.store import team_id_of

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


def _active(repo_file: Validation | None, uploaded: Validation | None) -> Literal["repo", "app"] | None:
    """Qué reglas usa el siguiente análisis (mismo criterio que reglas.run)."""
    if repo_file and repo_file.valid:
        return "repo"
    if uploaded and uploaded.valid:
        return "app"
    # Archivo del repo con errores y nada en la app: el análisis reporta el error
    return "repo" if repo_file else None


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
        active=_active(repo_file, uploaded),
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


# ───────────────────────── Revisión al cargar el repo (Nuevo análisis) ─────────────────────────


class PrecheckRequest(BaseModel):
    url: str = Field(max_length=300)
    branch: str = Field(default="main", max_length=200)
    # Reglas escritas en el formulario: se validan contra el árbol del repo (botón Validar del modal)
    content: str | None = Field(default=None, max_length=reglas.MAX_BYTES)


class Precheck(BaseModel):
    # "owner/repo"
    repo: str
    # Archivo del repo: valid | invalid | missing. unavailable = no se pudo leer (sin acceso, rama, GitHub caído)
    status: Literal["valid", "invalid", "missing", "unavailable"]
    message: str | None = None
    file: RepoRulesFile | None = None
    # El repo ya es un proyecto del equipo: sus reglas cargadas en la app
    project_id: str | None = None
    uploaded: UploadedRules | None = None
    # Lo que usará el análisis si no se cambia nada
    active: Literal["repo", "app"] | None = None
    # Plantilla con el nombre del repo y sus carpetas con código
    template: str
    # Validación de `content`, si se mandó
    checked: Validation | None = None


async def _github[T](call: Callable[[str | None], Awaitable[T]], token: str | None) -> T:
    """Con el token del usuario; si GitHub lo rechaza, sin él (repo público)."""
    try:
        return await call(token)
    except GithubAuthError:
        if not token:
            raise
        return await call(None)


def _unavailable(exc: Exception) -> str:
    if isinstance(exc, GithubError) and exc.status == 404:
        return "No se encontró el repositorio o la rama (o no tienes acceso). Las reglas se revisan al analizar."
    if isinstance(exc, GithubError) and exc.status in (403, 429):
        return "GitHub limitó las solicitudes: las reglas se revisan al analizar."
    return "No se pudo consultar GitHub: las reglas se revisan al analizar."


async def _repo_file(client: Client, token: str | None, name: str, branch: str) -> tuple[RepoRulesFile | None, list[str] | None, list[str]]:
    """(archivo de reglas del repo, archivos para revisar `rutas`, todos los archivos). Lanza si GitHub falla."""
    tree = await _github(lambda t: client.get_tree(t, name, branch), token)
    blobs = {e["path"]: e for e in tree.get("tree", []) if e.get("type") == "blob"}
    files = list(blobs)
    # Árbol truncado (repos enormes): las rutas no se pueden revisar con certeza
    check_files = None if tree.get("truncated") else files
    for path in reglas.LOCATIONS:
        entry = blobs.get(path)
        if entry is None:
            continue
        if entry.get("size", 0) > reglas.MAX_BYTES:
            return RepoRulesFile(valid=False, error=f"{path} es demasiado grande (máx. {reglas.MAX_BYTES // 1024} KB)", path=path, content=""), check_files, files
        raw = await _github(lambda t, p=path: client.get_file(t, name, p, branch), token)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return RepoRulesFile(valid=False, error=f"{path} no está en UTF-8", path=path, content=""), check_files, files
        return RepoRulesFile(**validate(text, check_files, name).model_dump(), path=path, content=text), check_files, files
    return None, check_files, files


@router.post("/api/reglas/revisar", response_model=Precheck)
async def precheck(body: PrecheckRequest, user_id: UserId, conn: Db, client: Client, accounts: Store) -> Precheck:
    """
    Reglas de negocio de un repo antes de analizarlo: lee su reglas_negocio.toml con la API de GitHub (sin clonar)
    y lo valida. Si el repo ya es un proyecto del equipo, también dice qué reglas tiene cargadas en la app.
    """
    m = REPO_URL.match(body.url.strip())
    if not m:
        raise ApiError(422, "invalid_url", "Usa la URL de un repositorio de GitHub (ej. https://github.com/equipo/proyecto)")
    branch = body.branch.strip() or "main"
    if not BRANCH.match(branch):
        raise ApiError(422, "invalid_branch", "El nombre de la rama no es válido")
    name = f"{m.group(1)}/{m.group(2)}"
    account = accounts.get(user_id)
    token = account.token if account else None

    status: Literal["valid", "invalid", "missing", "unavailable"]
    message: str | None = None
    repo_file: RepoRulesFile | None = None
    check_files: list[str] | None = None
    files: list[str] = []
    try:
        repo_file, check_files, files = await _repo_file(client, token, name, branch)
        status = "missing" if repo_file is None else "valid" if repo_file.valid else "invalid"
    except (GithubAuthError, GithubError, httpx.HTTPError) as exc:
        status, message = "unavailable", _unavailable(exc)

    project = conn.execute("SELECT id FROM repos WHERE team_id = ? AND name = ? COLLATE NOCASE", (team_id_of(conn, user_id), name)).fetchone()
    uploaded: UploadedRules | None = None
    if project:
        row = RulesStore(conn).upload(project["id"])
        if row:
            uploaded = UploadedRules(**validate(row["content"], check_files, name).model_dump(), content=row["content"], updated_at=row["updated_at"])
    return Precheck(
        repo=name, status=status, message=message, file=repo_file, project_id=project["id"] if project else None, uploaded=uploaded,
        active=_active(repo_file, uploaded), template=reglas.template_for(name, files),
        checked=validate(body.content, check_files, name) if body.content is not None else None,
    )
