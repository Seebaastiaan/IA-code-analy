"""
Prototipo del Sprint 3: diagnóstico con IA de UN archivo de un repositorio clonado.
POST /api/diagnostico {url, branch, file?} → clona el repo, elige el archivo y pide el diagnóstico a la IA.
"""

import re
import secrets
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.analysis.clone import CloneError, Cloner, clone_dir, python_files, read_python_file
from app.assistant.llm import LLM, LlmError, Turn
from app.config import Settings, get_settings
from app.diagnostico import prompts
from app.errors import ApiError

router = APIRouter(prefix="/api", tags=["diagnóstico"])

# Solo GitHub por HTTPS: https://github.com/owner/repo(.git). Otros hosts permitirían que el servidor
# clonara direcciones internas.
REPO_URL = re.compile(r"^https://(?:www\.)?github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)(?:\.git)?/?$", re.IGNORECASE)
# Nombre de rama válido para git; sin "-" inicial para que no se interprete como opción
BRANCH = re.compile(r"^(?!-)(?!.*\.\.)[A-Za-z0-9._/-]{1,200}$")

Config = Annotated[Settings, Depends(get_settings)]


def get_cloner() -> Cloner:
    return Cloner()


def get_llm(settings: Config) -> LLM:
    if not settings.gemini_api_key:
        raise ApiError(503, "llm_not_configured", "El diagnóstico no está configurado: falta GEMINI_API_KEY en backend/.env")
    return LLM(settings)


class DiagnosticoRequest(BaseModel):
    url: str
    branch: str = "main"
    # Ruta del .py dentro del repo; vacío = el primero que no sea de pruebas
    file: str | None = Field(default=None, max_length=500)


class Hallazgo(BaseModel):
    categoria: Literal["seg", "test", "prac"]
    severidad: Literal["alta", "media", "baja"]
    linea: int
    regla: str
    mensaje: str
    recomendacion: str


class Diagnostico(BaseModel):
    resumen: str
    score: int
    hallazgos: list[Hallazgo]


class DiagnosticoResponse(BaseModel):
    repo: str
    branch: str
    commit: str
    file: str
    # Archivos .py del repo (para elegir otro en el frontend)
    files: list[str]
    model: str
    diagnostico: Diagnostico


def _is_test(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return path.startswith("tests/") or "/tests/" in path or name.startswith("test_") or name.endswith("_test.py")


def _parse(data: dict, lines: int) -> Diagnostico:
    """Valida la respuesta de la IA; descarta hallazgos con líneas que no existen en el archivo."""
    try:
        diag = Diagnostico.model_validate(data)
    except ValueError as exc:
        raise ApiError(502, "llm_invalid", "La IA devolvió un diagnóstico con un formato inesperado. Intenta de nuevo.") from exc
    diag.score = max(0, min(100, diag.score))
    diag.hallazgos = [h for h in diag.hallazgos if 1 <= h.linea <= lines]
    return diag


@router.post("/diagnostico", response_model=DiagnosticoResponse)
def diagnosticar(
    body: DiagnosticoRequest, settings: Config, cloner: Annotated[Cloner, Depends(get_cloner)], llm: Annotated[LLM, Depends(get_llm)],
) -> DiagnosticoResponse:
    m = REPO_URL.match(body.url.strip())
    if not m:
        raise ApiError(422, "invalid_url", "Usa la URL de un repositorio de GitHub (ej. https://github.com/equipo/proyecto)")
    branch = body.branch.strip() or "main"
    if not BRANCH.match(branch):
        raise ApiError(422, "invalid_branch", "El nombre de la rama no es válido")
    name = f"{m.group(1)}/{m.group(2)}"
    # Un clon por repositorio: el nombre normalizado sirve de id de la carpeta
    repo_key = re.sub(r"[^a-z0-9]+", "-", name.lower())
    attempt = secrets.token_hex(4)
    try:
        result = cloner.clone(settings, repo_key, f"https://github.com/{name}", branch, None, attempt)
    except CloneError as err:
        raise ApiError(400, "clone_failed", f"{err.title}. {err.hint or err.detail}") from err
    cloner.promote(settings, repo_key, attempt)

    files = python_files(clone_dir(settings, repo_key))
    if not files:
        raise ApiError(422, "no_python", "El repositorio no tiene archivos .py")
    path = body.file or next((f for f in files if not _is_test(f) and not f.endswith("__init__.py")), files[0])
    try:
        content = read_python_file(settings, repo_key, path)
    except FileNotFoundError as exc:
        raise ApiError(404, "file_not_found", f"{path} no existe en el repositorio") from exc
    except ValueError as exc:
        raise ApiError(413, "file_too_large", "El archivo es demasiado grande para diagnosticarlo") from exc

    try:
        answer = llm.answer(prompts.SYSTEM, [Turn("user", prompts.user_prompt(path, content))], prompts.SCHEMA)
    except LlmError as exc:
        raise ApiError(503, "llm_unavailable", f"La IA no pudo responder: {exc}") from exc
    lines = len(content.replace("\r\n", "\n").split("\n"))
    return DiagnosticoResponse(
        repo=name, branch=branch, commit=result.commit, file=path, files=files, model=answer.model, diagnostico=_parse(answer.data, lines),
    )
