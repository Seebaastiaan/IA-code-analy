"""
Reglas de negocio sin pasos manuales (docs/PLAN_REGLAS_AUTOMATICO.md, paso 2 de «La experiencia»): al analizar, si el
repo no trae `reglas_negocio.toml` y el proyecto todavía no tiene reglas en la app, el programa busca el documento de
requisitos del clon (PDF o Word, los de `docs/` primero), saca las reglas con la IA y las guarda en el proyecto.

Así nadie tiene que descargar el archivo, subirlo en Configuración ni hacer commit: las reglas quedan en el proyecto y se
usan en cada análisis. Entran como borrador (no cuentan hasta aprobarlas o hasta «Preparar todo»). Nunca pisa lo que el
equipo ya guardó y nunca detiene el análisis: si algo falla, lo dice en una línea y el equipo puede importarlas a mano.
"""

import logging
from dataclasses import dataclass

from app.analyses import reglas
from app.analyses.reglas_store import RulesStore
from app.analyses.workspace import Workspace
from app.assistant.llm import LLM, LlmError
from app.config import Settings
from app.db import session
from app.projects import reglas_importar as importar
from app.projects import reglas_respuestas as respuestas

log = logging.getLogger(__name__)


@dataclass
class AutoImport:
    # El documento de donde salieron (o se intentaron sacar) las reglas
    document: str
    # Línea para la terminal del análisis
    line: str
    saved: bool = False


def pending_document(settings: Settings, repo_id: str) -> str | None:
    """El documento del que se sacarían las reglas, o None si no hace falta (o no se puede) importarlas solas."""
    if not settings.gemini_api_key:
        return None
    ws = Workspace(settings, repo_id)
    if not ws.exists():
        return None
    try:
        # El repo trae su archivo de reglas (aunque tenga errores): manda el repo, no se importa nada
        if reglas.find(ws.root):
            return None
    except reglas.RulesError:
        return None
    with session(settings.database_path) as conn:
        if RulesStore(conn).upload(repo_id):
            return None
    documents = importar.find_documents(ws.sizes_by_extension(importar.EXTENSIONS))
    return documents[0] if documents else None


def run(settings: Settings, repo_id: str, project: str, user_id: str | None, document: str) -> AutoImport:
    """Bloqueante (red). Saca las reglas de `document` y las guarda en la app. Nunca lanza."""
    try:
        full = Workspace(settings, repo_id).resolve(document)
        if full.stat().st_size > importar.MAX_DOC_BYTES:
            return AutoImport(document, f"  reglas: {document} pesa más de {importar.MAX_DOC_BYTES // (1024 * 1024)} MB; súbelo en Configuración → Reglas")
        llm = LLM(settings)
        result = importar.extract(llm, project, document, full.read_bytes())
    except importar.DocumentError as exc:
        return AutoImport(document, f"  reglas: no se pudo leer {document} ({exc})")
    except LlmError as exc:
        log.warning("No se pudieron sacar las reglas de %s en %s: %s", document, repo_id, exc)
        return AutoImport(document, f"  reglas: la IA no pudo leer {document} ahora; vuelve a analizar o impórtalo en Configuración → Reglas")
    except Exception:
        log.exception("Fallo al sacar las reglas de %s en %s", document, repo_id)
        return AutoImport(document, f"  reglas: no se pudieron sacar de {document}; impórtalo en Configuración → Reglas")
    if not result.count:
        return AutoImport(document, f"  reglas: {document} no tiene reglas de negocio que se puedan comprobar")
    content = result.content
    with session(settings.database_path) as conn:
        store = RulesStore(conn)
        # Mientras corría la IA alguien pudo guardar reglas a mano: lo del equipo gana
        if store.upload(repo_id):
            return AutoImport(document, "  reglas: el proyecto ya tiene reglas guardadas; no se reemplazaron")
        try:
            reglas.parse(content)
        except reglas.RulesError:
            # Con contradicciones el archivo no es válido hasta que el equipo decida: se guarda igual para decidirlo en
            # Configuración → Reglas, sin perder lo que la IA ya leyó
            valid = False
        else:
            valid = True
            # Lo que el equipo ya contestó en otra importación no se vuelve a preguntar
            try:
                # Por texto y por significado (la IA redacta la misma duda distinto en cada importación)
                content, _ = respuestas.apply(content, [dict(r) for r in store.answers(repo_id)], lambda texts: llm.embed(texts, "SEMANTIC_SIMILARITY"))
            except reglas.RulesError:
                pass
        store.save_upload(repo_id, content, user_id)
    n = f"{result.count} regla{'s' if result.count != 1 else ''}"
    if not valid:
        line = f"  reglas: saqué {n} de {document}; el documento se contradice en {len(result.contradictions) or 'algunos'} punto(s): decide cuál vale en Configuración → Reglas"
    else:
        line = f"  reglas: saqué {n} de {document} y quedaron guardadas en el proyecto; revísalas en Configuración → Reglas"
    return AutoImport(document, line, saved=True)
