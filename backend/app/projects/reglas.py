"""
Configuración → Reglas de negocio (docs/PROPUESTA_REGLAS_NEGOCIO.md §2 y §6, ADR-003).

Las reglas son de cada proyecto (repo): la fuente oficial es su `reglas_negocio.toml`. Desde la app se pueden
cargar reglas de apoyo para ese proyecto (mientras se redactan, o para corregir un archivo del repo con errores): se
validan igual —también contra las rutas de su repositorio— y se usan en su análisis si el repo no tiene el archivo o
el suyo no es válido. No hay reglas generales.

`POST /api/reglas/revisar` revisa las reglas al cargar el repo (Nuevo análisis), antes de clonar: lee el archivo
con la API de GitHub y lo valida con el mismo parser.

`POST /api/reglas/importar` saca las reglas de un documento de requisitos (PDF, Word, Markdown) con Gemini
(app.projects.reglas_importar) y devuelve el `reglas_negocio.toml` para revisarlo en el editor; no guarda nada.
"""

import asyncio
import base64
import binascii
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from app.analyses import reglas
from app.analyses.access import Analyses, UserId, require_repo
from app.analyses.reglas_store import RulesStore
from app.analyses.workspace import Workspace
from app.analysis.router import BRANCH, REPO_URL, Config, Db
from app.assistant.llm import LLM, LlmError
from app.assistant.router import get_llm
from app.errors import ApiError
from app.github.client import GithubAuthError, GithubError
from app.github.deps import Client, Store
from app.projects import reglas_importar as importar
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
    # Reglas que se contradicen o están duplicadas, y (revisadas contra el repositorio del proyecto) `rutas` que no
    # existen en él. No bloquean el guardado
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
    # Documentos de requisitos de la copia del repo (se pueden importar) y si hay IA para importarlos
    documents: list[str] = Field(default_factory=list)
    can_import: bool = False


def validate(text: str, files: list[str] | None = None, project: str = "") -> Validation:
    """`files` = archivos del clon del proyecto (None = sin clonar: las rutas no se revisan)."""
    try:
        rs = reglas.parse(text)
    except reglas.RulesError as exc:
        return Validation(valid=False, error=str(exc))
    return Validation(
        valid=True, project=rs.project,
        rules=[RulePreview(id=r.id, title=r.title, severity=r.severity, pattern=bool(r.forbidden or r.required)) for r in rs.rules],
        warnings=(reglas.conflicts(rs.rules) + (reglas.missing_paths(rs, files, project) if files is not None else []))[: reglas.MAX_WARNINGS],
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


def _documents(ws: Workspace, files: list[str] | None) -> list[str]:
    """Documentos de requisitos de la copia del repo (los de `docs/` primero)."""
    if not files:
        return []
    return importar.find_documents({f: (ws.root / f).stat().st_size for f in files if f.lower().endswith(importar.EXTENSIONS)})


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
        documents=_documents(ws, files), can_import=bool(settings.gemini_api_key),
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
    # Documentos de requisitos del árbol (PDF, Word, Markdown) y si hay IA para importarlos
    documents: list[str] = Field(default_factory=list)
    can_import: bool = False


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


async def _repo_file(client: Client, token: str | None, name: str, branch: str) -> tuple[RepoRulesFile | None, list[str] | None, list[str], list[str]]:
    """
    (archivo de reglas del repo, archivos para revisar `rutas`, todos los archivos, documentos de requisitos).
    Lanza si GitHub falla.
    """
    tree = await _github(lambda t: client.get_tree(t, name, branch), token)
    blobs = {e["path"]: e for e in tree.get("tree", []) if e.get("type") == "blob"}
    files = list(blobs)
    documents = importar.find_documents({p: int(e.get("size") or 0) for p, e in blobs.items()})
    # Árbol truncado (repos enormes): las rutas no se pueden revisar con certeza
    check_files = None if tree.get("truncated") else files
    for path in reglas.LOCATIONS:
        entry = blobs.get(path)
        if entry is None:
            continue
        if entry.get("size", 0) > reglas.MAX_BYTES:
            return RepoRulesFile(valid=False, error=f"{path} es demasiado grande (máx. {reglas.MAX_BYTES // 1024} KB)", path=path, content=""), check_files, files, documents
        raw = await _github(lambda t, p=path: client.get_file(t, name, p, branch), token)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return RepoRulesFile(valid=False, error=f"{path} no está en UTF-8", path=path, content=""), check_files, files, documents
        return RepoRulesFile(**validate(text, check_files, name).model_dump(), path=path, content=text), check_files, files, documents
    return None, check_files, files, documents


@router.post("/api/reglas/revisar", response_model=Precheck)
async def precheck(body: PrecheckRequest, user_id: UserId, conn: Db, client: Client, accounts: Store, settings: Config) -> Precheck:
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
    documents: list[str] = []
    try:
        repo_file, check_files, files, documents = await _repo_file(client, token, name, branch)
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
        documents=documents, can_import=bool(settings.gemini_api_key),
    )


# ───────────────────────── Importar desde un documento de requisitos ─────────────────────────


# 10 MB en base64, con margen
MAX_BASE64 = importar.MAX_DOC_BYTES * 4 // 3 + 1024


class ImportRequest(BaseModel):
    """
    Una de tres fuentes: el repo en GitHub (`url` + `branch` + `path`, Nuevo análisis), la copia de un proyecto
    (`project_id` + `path`, Configuración) o un archivo subido (`filename` + `data`; `project_id` opcional da el nombre).
    """

    url: str | None = Field(default=None, max_length=300)
    branch: str = Field(default="main", max_length=200)
    project_id: str | None = Field(default=None, max_length=100)
    path: str | None = Field(default=None, max_length=500)
    filename: str | None = Field(default=None, max_length=255)
    # Contenido del archivo subido, en base64
    data: str | None = Field(default=None, max_length=MAX_BASE64)


class ImportedRules(BaseModel):
    # reglas_negocio.toml para revisar en el editor (no se guarda)
    content: str
    count: int
    # Ambigüedades del documento que encontró la IA
    doubts: list[str]
    # Reglas que el documento contradice («RN-004 (§4.2) y RN-009 (§7.1): …»). Van marcadas en `content` con
    # `# CONTRADICCIÓN` y el archivo no es válido hasta que el equipo deje una de cada par
    contradictions: list[str] = Field(default_factory=list)
    source: str
    validation: Validation
    model: str


def _repo_name(url: str | None) -> str | None:
    m = REPO_URL.match((url or "").strip())
    return f"{m.group(1)}/{m.group(2)}" if m else None


async def _document(body: ImportRequest, user_id: str, client: Client, accounts: Store, store: Analyses, settings) -> tuple[str, str, bytes]:
    """(nombre del proyecto, nombre del documento, contenido). DocumentError o ApiError si no se puede leer."""
    if body.data is not None:
        if not body.filename:
            raise ApiError(422, "invalid_request", "Falta el nombre del archivo")
        importar.kind_of(body.filename)
        if len(body.data) > MAX_BASE64:
            raise importar.DocumentError("file_too_large", f"El documento pesa más de {importar.MAX_DOC_BYTES // (1024 * 1024)} MB")
        try:
            data = base64.b64decode(body.data, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ApiError(422, "invalid_document", "El archivo no llegó completo; vuelve a subirlo") from exc
        project = require_repo(store, user_id, body.project_id)["name"] if body.project_id else _repo_name(body.url) or "Mi proyecto"
        return project, body.filename, data
    if not body.path:
        raise ApiError(422, "invalid_request", "Indica el documento: su ruta en el repositorio o un archivo subido")
    importar.kind_of(body.path)
    if body.project_id:
        repo = require_repo(store, user_id, body.project_id)
        full = Workspace(settings, repo["id"]).resolve(body.path)
        if not full.is_file():
            raise ApiError(404, "not_found", f"No existe {body.path} en la copia del repositorio")
        if full.stat().st_size > importar.MAX_DOC_BYTES:
            raise importar.DocumentError("file_too_large", f"El documento pesa más de {importar.MAX_DOC_BYTES // (1024 * 1024)} MB")
        return repo["name"], body.path, full.read_bytes()
    name = _repo_name(body.url)
    if not name:
        raise ApiError(422, "invalid_url", "Usa la URL de un repositorio de GitHub (ej. https://github.com/equipo/proyecto)")
    branch = body.branch.strip() or "main"
    if not BRANCH.match(branch):
        raise ApiError(422, "invalid_branch", "El nombre de la rama no es válido")
    account = accounts.get(user_id)
    try:
        data = await _github(lambda t: client.get_file(t, name, body.path, branch), account.token if account else None)
    except GithubError as exc:
        if exc.status == 404:
            raise ApiError(404, "not_found", f"No se encontró {body.path} en {name} ({branch})") from exc
        raise ApiError(502, "github_unavailable", "No se pudo leer el documento de GitHub; intenta de nuevo") from exc
    except (GithubAuthError, httpx.HTTPError) as exc:
        raise ApiError(502, "github_unavailable", "No se pudo leer el documento de GitHub; intenta de nuevo") from exc
    return name, body.path, data


LLM_ERRORS = {
    "quota": ("llm_rate_limited", "La IA alcanzó su límite de uso. Intenta de nuevo en un minuto."),
    "busy": ("llm_busy", "Los modelos de IA están saturados en este momento. Intenta de nuevo en unos segundos."),
}
DOCUMENT_STATUS = {"unsupported_type": 415, "file_too_large": 413}


@router.post("/api/reglas/importar", response_model=ImportedRules)
async def import_document(
    body: ImportRequest, user_id: UserId, client: Client, accounts: Store, store: Analyses, settings: Config,
    llm: Annotated[LLM, Depends(get_llm)],
) -> ImportedRules:
    """
    Reglas de negocio desde un documento de requisitos: Gemini las propone y aquí se arma y valida el
    reglas_negocio.toml. No guarda nada: el usuario lo revisa en el editor y lo usa o lo descarga como siempre.
    """
    try:
        project, source, data = await _document(body, user_id, client, accounts, store, settings)
        result = await asyncio.to_thread(importar.extract, llm, project, source, data)
    except importar.DocumentError as exc:
        raise ApiError(DOCUMENT_STATUS.get(exc.code, 422), exc.code, str(exc)) from exc
    except LlmError as exc:
        code, message = LLM_ERRORS.get(exc.kind or "", ("llm_unavailable", f"La IA no pudo leer el documento: {exc}"))
        raise ApiError(503, code, message) from exc
    if not result.count:
        detail = f" {result.doubts[0]}" if result.doubts else ""
        raise ApiError(422, "no_rules_found", f"No se encontraron reglas de negocio en {source}.{detail}")
    return ImportedRules(
        content=result.content, count=result.count, doubts=result.doubts, contradictions=result.contradictions, source=source,
        validation=validate(result.content, None, project), model=result.model,
    )
