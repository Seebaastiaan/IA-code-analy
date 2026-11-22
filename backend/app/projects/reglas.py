"""
Configuración → Reglas de negocio (docs/PROPUESTA_REGLAS_NEGOCIO.md §2 y §6, ADR-003).

Las reglas son de cada proyecto (repo): la fuente oficial es su `reglas_negocio.toml`. Desde la app se pueden
cargar reglas de apoyo para ese proyecto (mientras se redactan, o para corregir un archivo del repo con errores): se
validan igual —también contra las rutas de su repositorio— y se usan en su análisis si el repo no tiene el archivo o
el suyo no es válido. No hay reglas generales.

`POST /api/reglas/revisar` revisa las reglas al cargar el repo (Nuevo análisis), antes de clonar: lee el archivo
con la API de GitHub y lo valida con el mismo parser.

`POST /api/reglas/importar` saca las reglas de un documento de requisitos (PDF o Word) con Gemini
(app.projects.reglas_importar) y devuelve el `reglas_negocio.toml` para revisarlo en el editor; no guarda nada.
"""

import asyncio
import base64
import binascii
import json
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from app.analyses import reglas
from app.analyses.access import Analyses, UserId, require_repo
from app.analyses.reglas_store import EvidenceStore, RulesStore, RuleTestsStore
from app.analyses.workspace import Workspace
from app.analysis.router import BRANCH, REPO_URL, Config, Db
from app.assistant.llm import LLM, LlmError
from app.assistant.router import get_llm
from app.errors import ApiError
from app.github.client import GithubAuthError, GithubError
from app.github.deps import Client, Store
from app.projects import reglas_arnes as arnes
from app.projects import reglas_concordancia as concordancia
from app.projects import reglas_documento as documento
from app.projects import reglas_fuerza as fuerza
from app.projects import reglas_importar as importar
from app.projects import reglas_respuestas as respuestas
from app.teams.store import team_id_of

router = APIRouter(tags=["reglas de negocio"])


class RulesContent(BaseModel):
    content: str = Field(max_length=reglas.MAX_BYTES)


class ScenarioOut(BaseModel):
    given: str
    when: str
    then: str


class RulePreview(BaseModel):
    id: str
    title: str
    severity: str
    # Tiene `prohibido` u `obligatorio`; sin patrón la verifican sus pruebas
    pattern: bool
    # Formato v2 (PROPUESTA_REGLAS_VERIFICABLES.md §5): la tabla de aprobación
    description: str = ""
    tipo: str | None = None
    # borrador | aprobada: solo las aprobadas se verifican
    status: Literal["borrador", "aprobada"] = "aprobada"
    source: str | None = None
    doubts: list[str] = Field(default_factory=list)
    scenarios: list[ScenarioOut] = Field(default_factory=list)
    # Frase del documento de requisitos y si el programa la encontró ahí (null = no se pudo comprobar, p. ej. un PDF)
    quote: str | None = None
    quote_ok: bool | None = None
    # "programa" si la aprobó el programa solo (se puede revertir); null si la aprobó el equipo
    approved_by: str | None = None


def preview(r: reglas.BusinessRule) -> RulePreview:
    return RulePreview(
        id=r.id, title=r.title, severity=r.severity, pattern=bool(r.forbidden or r.required), description=r.description,
        tipo=r.tipo, status=r.status, source=r.source or r.story, doubts=list(r.doubts), quote=r.quote, quote_ok=r.quote_ok, approved_by=r.approved_by,
        scenarios=[ScenarioOut(given=s.given, when=s.when, then=s.then) for s in r.scenarios],
    )


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
    # Avisos de la última acción (reglas que no se pudieron aprobar y por qué)
    messages: list[str] = Field(default_factory=list)


class RuleStates(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=reglas.MAX_RULES)
    status: Literal["borrador", "aprobada"]
    # Quién aprueba: el equipo o el programa solo («Preparar todo»); lo que aprueba el programa se marca y se revierte en un clic
    by: Literal["equipo", "programa"] = "equipo"


class DoubtAnswer(BaseModel):
    # La duda tal como está abierta y su respuesta: «si», «no» o, si la pregunta no es de sí o no, lo que escribe el equipo
    doubt: str = Field(max_length=reglas.MAX_DOUBT)
    answer: str = Field(min_length=1, max_length=300)


class RuleDoubts(BaseModel):
    # Las dudas que siguen abiertas (quitar una = resolverla)
    doubts: list[str] = Field(max_length=reglas.MAX_DOUBTS)


def validate(text: str, files: list[str] | None = None, project: str = "") -> Validation:
    """`files` = archivos del clon del proyecto (None = sin clonar: las rutas no se revisan)."""
    try:
        rs = reglas.parse(text)
    except reglas.RulesError as exc:
        return Validation(valid=False, error=str(exc))
    return Validation(
        valid=True, project=rs.project, rules=[preview(r) for r in rs.rules],
        warnings=(rs.warnings + reglas.conflicts(rs.rules) + (reglas.missing_paths(rs, files, project) if files is not None else []))[: reglas.MAX_WARNINGS],
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


def _documents(ws: Workspace) -> list[str]:
    """Documentos de requisitos (PDF o Word) de la copia del repo, los de `docs/` primero."""
    return importar.find_documents(ws.sizes_by_extension(importar.EXTENSIONS))


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
        documents=_documents(ws), can_import=bool(settings.gemini_api_key),
    )


@router.get("/api/projects/{project_id}/reglas", response_model=ProjectRules)
def get_rules(project_id: str, store: Analyses, user_id: UserId, settings: Config) -> ProjectRules:
    require_repo(store, user_id, project_id)
    return _project_rules(store, settings, project_id)


def _embedder(settings: Config) -> respuestas.Embed | None:
    """Embeddings de Gemini para reconocer la misma duda redactada distinto; None si no hay clave."""
    if not settings.gemini_api_key:
        return None
    llm = LLM(settings)
    return lambda texts: llm.embed(texts, "SEMANTIC_SIMILARITY")


@router.put("/api/projects/{project_id}/reglas", response_model=ProjectRules)
def upload_rules(project_id: str, body: RulesContent, store: Analyses, user_id: UserId, settings: Config) -> ProjectRules:
    """Guarda reglas de apoyo en la app. Solo se aceptan válidas (`422 invalid_rules` con la línea del error)."""
    require_repo(store, user_id, project_id)
    result = validate(body.content)
    if not result.valid:
        raise ApiError(422, "invalid_rules", result.error or "Reglas no válidas")
    rules_store = RulesStore(store.conn)
    # Lo que el equipo ya contestó antes (misma pregunta de la misma regla) no se vuelve a preguntar
    content, remembered = respuestas.apply(body.content, [dict(r) for r in rules_store.answers(project_id)], _embedder(settings))
    rules_store.save_upload(project_id, content, user_id)
    return _project_rules(store, settings, project_id).model_copy(update={"messages": remembered})


@router.delete("/api/projects/{project_id}/reglas", response_model=ProjectRules)
def delete_rules(project_id: str, store: Analyses, user_id: UserId, settings: Config) -> ProjectRules:
    require_repo(store, user_id, project_id)
    RulesStore(store.conn).delete_upload(project_id)
    return _project_rules(store, settings, project_id)


REPO_COPY_NOTE = (
    "Guardado en la copia del proyecto, no en GitHub: descarga el archivo (Descargar para el repo) y haz commit. Un análisis "
    "nuevo vuelve a clonar el repositorio y su archivo manda otra vez"
)


def _editable(store: Analyses, settings: Config, project_id: str, user_id: str) -> tuple[str, reglas.RuleSet, Callable[[str], None], bool]:
    """
    (texto, reglas, cómo guardar, ¿es la copia del repo?) de las reglas que usa el análisis. Las cargadas en la app se
    guardan en la app. Las del repositorio se guardan en su copia de trabajo, con respaldo (como el editor): GitHub no se
    toca, así que hay que descargar el archivo y hacer commit.
    """
    current = _project_rules(store, settings, project_id)
    if current.active == "repo":
        if current.repo is None or not current.repo.valid:
            raise ApiError(409, "invalid_repo_rules", f"El {current.repo.path if current.repo else reglas.FILENAME} del repositorio tiene errores: corrígelo primero")
        ws = Workspace(settings, project_id)
        path, text = current.repo.path, current.repo.content
        try:
            return text, reglas.parse(text), lambda new: ws.write(path, new), True
        except reglas.RulesError as exc:
            raise ApiError(422, "invalid_rules", str(exc)) from exc
    text = RulesStore(store.conn).uploaded_text(project_id)
    if not text:
        raise ApiError(409, "no_rules", "El proyecto no tiene reglas cargadas en la app")
    try:
        return text, reglas.parse(text), lambda new: RulesStore(store.conn).save_upload(project_id, new, user_id), False
    except reglas.RulesError as exc:
        raise ApiError(422, "invalid_rules", str(exc)) from exc


@router.post("/api/projects/{project_id}/reglas/estado", response_model=ProjectRules)
def set_states(project_id: str, body: RuleStates, store: Analyses, user_id: UserId, settings: Config) -> ProjectRules:
    """
    Aprueba (o vuelve a borrador) las reglas de `ids` en las reglas cargadas en la app. Una regla con dudas abiertas no se
    aprueba: se dice por qué en `messages` (PROPUESTA_REGLAS_VERIFICABLES.md §5).
    """
    require_repo(store, user_id, project_id)
    text, rs, save, in_repo = _editable(store, settings, project_id, user_id)
    by_id = {r.id: r for r in rs.rules}
    unknown = [i for i in body.ids if i not in by_id]
    if unknown:
        raise ApiError(404, "unknown_rule", f"{', '.join(unknown)} no está en las reglas del proyecto")
    messages: list[str] = []
    changed = False
    for rid in dict.fromkeys(body.ids):
        rule = by_id[rid]
        if rule.status == body.status:
            continue
        if body.status == "aprobada" and rule.doubts:
            messages.append(f"{rid}: tiene {len(rule.doubts)} duda(s) abierta(s); resuélvelas antes de aprobarla")
            continue
        by_program = body.status == "aprobada" and body.by == "programa"
        text = reglas.set_fields(text, rid, {"estado": body.status, "aprobada_por": "programa" if by_program else None})
        changed = True
    if changed:
        save(text)
        if in_repo:
            messages.append(REPO_COPY_NOTE)
    return _project_rules(store, settings, project_id).model_copy(update={"messages": messages})


@router.put("/api/projects/{project_id}/reglas/{rule_id}/dudas", response_model=ProjectRules)
def set_doubts(project_id: str, rule_id: str, body: RuleDoubts, store: Analyses, user_id: UserId, settings: Config) -> ProjectRules:
    """Las dudas que siguen abiertas de una regla: quitar una es resolverla (la respuesta va en la descripción)."""
    require_repo(store, user_id, project_id)
    text, rs, save, in_repo = _editable(store, settings, project_id, user_id)
    if rule_id not in {r.id for r in rs.rules}:
        raise ApiError(404, "unknown_rule", f"{rule_id} no está en las reglas del proyecto")
    doubts = [d.strip()[: reglas.MAX_DOUBT] for d in body.doubts if d.strip()]
    try:
        text = reglas.set_fields(text, rule_id, {"dudas": doubts})
    except reglas.RulesError as exc:
        raise ApiError(422, "invalid_rules", str(exc)) from exc
    save(text)
    return _project_rules(store, settings, project_id).model_copy(update={"messages": [REPO_COPY_NOTE] if in_repo else []})


@router.post("/api/projects/{project_id}/reglas/{rule_id}/respuesta", response_model=ProjectRules)
def answer_doubt(project_id: str, rule_id: str, body: DoubtAnswer, store: Analyses, user_id: UserId, settings: Config) -> ProjectRules:
    """
    Contesta una duda de una regla con sí o no: la duda se cierra, la respuesta queda en la descripción de la regla y en la
    memoria del proyecto (una importación nueva con la misma pregunta se contesta sola).
    """
    require_repo(store, user_id, project_id)
    text, rs, save, in_repo = _editable(store, settings, project_id, user_id)
    rule = next((r for r in rs.rules if r.id == rule_id), None)
    if rule is None:
        raise ApiError(404, "unknown_rule", f"{rule_id} no está en las reglas del proyecto")
    if body.doubt not in rule.doubts:
        raise ApiError(409, "unknown_doubt", f"{rule_id} ya no tiene esa duda abierta")
    try:
        text = reglas.set_fields(text, rule_id, {
            "descripcion": respuestas.with_note(rule.description, body.doubt, body.answer),
            "dudas": [d for d in rule.doubts if d != body.doubt],
        })
    except reglas.RulesError as exc:
        raise ApiError(422, "invalid_rules", str(exc)) from exc
    save(text)
    RulesStore(store.conn).save_answer(project_id, respuestas.key_of(rule.title, body.doubt), rule.title, body.doubt, body.answer, user_id)
    return _project_rules(store, settings, project_id).model_copy(update={"messages": [REPO_COPY_NOTE] if in_repo else []})


class SentenceBody(BaseModel):
    text: str = Field(min_length=1, max_length=importar.MAX_SENTENCE)


class ControlItem(BaseModel):
    rule_id: str
    title: str
    expected: Literal["cumple", "viola"] | None
    status: str | None
    outcome: Literal["acerto", "fallo", "sin_resultado"] | None
    # Con qué solidez se comprobó en el último análisis: alta | media | baja | ninguna
    confidence: str | None


class Concordance(BaseModel):
    items: list[ControlItem]
    # Reglas con caso de control, y de ellas las que el programa acertó, falló o no pudo comprobar
    known: int
    hits: int
    misses: int
    unverified: int
    # Número del último análisis con el que se compara (None = todavía no hay)
    report_num: int | None


class ExpectedBody(BaseModel):
    expected: Literal["cumple", "viola"] | None


def _crosscheck(test, code_hash: str, evidence, commit: str | None) -> str | None:
    """coincide | discrepa: la corrida de la prueba actual contra la lectura del código de esa versión de la regla y del commit."""
    from app.projects import pruebas as rutas_pruebas
    from app.projects import reglas_evidencia as evidencia

    if test["run_hash"] != code_hash or test["run_status"] != "hecho" or not test["run_result"] or evidence is None:
        return None
    if evidence["rule_hash"] != test["rule_hash"] or (commit is not None and evidence["commit_sha"] != commit):
        return None
    ev = evidencia.loads(evidence["data"])
    verdict = json.loads(test["run_result"]).get("verdict")
    if ev is None or verdict not in ("cumple", "no_cumple"):
        return None
    key = (verdict, ev.verdict)
    return "coincide" if key in rutas_pruebas.CROSS_AGREE else "discrepa" if key in rutas_pruebas.CROSS_DISAGREE else None


def _concordance(store: Analyses, settings: Config, project_id: str) -> Concordance:
    current = _project_rules(store, settings, project_id)
    source = current.repo if current.active == "repo" else current.uploaded
    rules = [(r.id, r.title) for r in source.rules] if source and source.valid else []
    rules_store = RulesStore(store.conn)
    latest = store.latest_report(project_id)
    results = {r["rule_id"]: (r["status"], r["level"]) for r in rules_store.results(latest["id"])} if latest else {}
    strength: dict[str, str] = {}
    cross: dict[str, str] = {}
    evidences = EvidenceStore(store.conn).all(project_id)
    commit = latest["commit_sha"] if latest else None
    for row in RuleTestsStore(store.conn).all(project_id):
        current = arnes.code_hash(row["code"])
        # Solo vale la prueba de fuerza de la versión actual de la prueba
        done = row["strength_status"] == "hecho" and row["strength_hash"] == current and fuerza.loads(row["strength_result"])
        if done:
            strength[row["rule_id"]] = done.status
        agree = _crosscheck(row, current, evidences.get(row["rule_id"]), commit)
        if agree:
            cross[row["rule_id"]] = agree
    items = concordancia.build(rules, rules_store.expected(project_id), results, strength, cross)
    known = [i for i in items if i.expected]
    return Concordance(
        items=[ControlItem(**i.__dict__) for i in items], known=len(known), hits=sum(i.outcome == "acerto" for i in known),
        misses=sum(i.outcome == "fallo" for i in known), unverified=sum(i.outcome == "sin_resultado" for i in known),
        report_num=latest["num"] if latest else None,
    )


@router.get("/api/projects/{project_id}/reglas/concordancia", response_model=Concordance)
def get_concordance(project_id: str, store: Analyses, user_id: UserId, settings: Config) -> Concordance:
    """Las reglas con su caso de control y cuántas acertó el programa en el último análisis."""
    require_repo(store, user_id, project_id)
    return _concordance(store, settings, project_id)


@router.put("/api/projects/{project_id}/reglas/{rule_id}/esperado", response_model=Concordance)
def set_expected(project_id: str, rule_id: str, body: ExpectedBody, store: Analyses, user_id: UserId, settings: Config) -> Concordance:
    """Caso de control: lo que el equipo sabe de la regla (`cumple`, `viola` o null para quitarlo). No cambia resultados."""
    require_repo(store, user_id, project_id)
    current = _concordance(store, settings, project_id)
    if rule_id not in {i.rule_id for i in current.items}:
        raise ApiError(404, "unknown_rule", f"{rule_id} no está en las reglas del proyecto")
    RulesStore(store.conn).set_expected(project_id, rule_id, body.expected, user_id)
    return _concordance(store, settings, project_id)


@router.post("/api/projects/{project_id}/reglas/redactar", response_model=ProjectRules)
async def write_rule(
    project_id: str, body: SentenceBody, store: Analyses, user_id: UserId, settings: Config, llm: Annotated[LLM, Depends(get_llm)],
) -> ProjectRules:
    """
    «Escribe una regla con tus palabras»: la IA la convierte en una regla verificable (con ejemplos y dudas) y se agrega
    en borrador a las reglas del proyecto. Sin reglas todavía, arma el archivo con ella.
    """
    repo = require_repo(store, user_id, project_id)
    current = _project_rules(store, settings, project_id)
    if current.active == "repo" or current.uploaded:
        text, _, save, in_repo = _editable(store, settings, project_id, user_id)
    else:
        text, in_repo = None, False

        def save(new: str) -> None:
            RulesStore(store.conn).save_upload(project_id, new, user_id)

    try:
        content, new_id, _ = await asyncio.to_thread(importar.draft_from_sentence, llm, repo["name"], body.text, text)
    except ValueError as exc:
        raise ApiError(422, "invalid_sentence", str(exc)) from exc
    except LlmError as exc:
        code, message = LLM_ERRORS.get(exc.kind or "", ("llm_unavailable", f"La IA no pudo redactar la regla: {exc}"))
        raise ApiError(503, code, message) from exc
    try:
        reglas.parse(content)
    except reglas.RulesError as exc:
        raise ApiError(422, "invalid_rules", str(exc)) from exc
    save(content)
    return _project_rules(store, settings, project_id).model_copy(update={"messages": [f"{new_id} agregada en borrador: revísala y apruébala", *([REPO_COPY_NOTE] if in_repo else [])]})


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


@router.get("/api/projects/{project_id}/reglas/documento")
def readable_document(project_id: str, store: Analyses, user_id: UserId, settings: Config, formato: Literal["html", "md"] = "html") -> Response:
    """
    Las reglas que usa el análisis como un documento para leer y presentar (HTML imprimible o Markdown), sin TOML:
    resumen, cómo leerlo y, por regla, sus ejemplos, dudas y fuente (reglas_documento.py).
    """
    require_repo(store, user_id, project_id)
    current = _project_rules(store, settings, project_id)
    source = current.repo if current.active == "repo" else current.uploaded
    if source is None or not source.valid:
        raise ApiError(409, "no_rules", "El proyecto no tiene reglas válidas para armar el documento")
    rule_set = reglas.parse(source.content)
    if formato == "md":
        return Response(documento.markdown(rule_set), media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="reglas_de_negocio.md"'})
    return Response(documento.html(rule_set), media_type="text/html; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="reglas_de_negocio.html"'})


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
    # Documentos de requisitos del árbol (PDF o Word) y si hay IA para importarlos
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
