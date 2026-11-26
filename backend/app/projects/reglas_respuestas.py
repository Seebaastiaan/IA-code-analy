"""
Dudas de las reglas como preguntas de sí o no, con memoria (docs/PLAN_REGLAS_AUTOMATICO.md, paso 4).

Una duda («¿el límite incluye el valor exacto?») se contesta con Sí o No. La respuesta se anota en la descripción de la
regla (así queda en el documento y la lee la IA que escribe la prueba) y se guarda en la memoria del proyecto: si una
importación nueva trae la misma pregunta de la misma regla, se contesta sola y no se vuelve a preguntar.
Las preguntas se reconocen por su texto (sin acentos ni signos, tolerando pequeñas diferencias de redacción de la IA) y,
si no coincide, por su significado (embeddings): en una corrida real con Gemini la misma duda salió redactada distinto
cada vez y solo 1 de 6 pares pasaba el parecido de texto, mientras que con embeddings la misma pregunta daba ≥ 0,92 y
preguntas distintas ≤ 0,82.
"""

import hashlib
import logging
from collections.abc import Callable
from difflib import SequenceMatcher

from app.analyses import reglas
from app.projects.reglas_importar import _fold

ANSWERS = {"si": "Sí", "no": "No"}
# Qué tan parecida debe ser una pregunta (y el título de su regla) para darla por la misma
QUESTION_MATCH = 0.8
TITLE_MATCH = 0.6
# Por significado (coseno de los embeddings): la pregunta y, como cerrojo, el título de su regla
SEMANTIC_QUESTION = 0.88
SEMANTIC_TITLE = 0.75

log = logging.getLogger(__name__)
# Convierte textos en vectores normalizados (una fila por texto); None = sin embeddings, solo se compara el texto
Embed = Callable[[list[str]], "object"]


def key_of(title: str, question: str) -> str:
    return hashlib.sha1(f"{_fold(title)}|{_fold(question)}".encode()).hexdigest()[:16]


def _similar(a: str, b: str, limit: float) -> bool:
    a, b = _fold(a), _fold(b)
    return bool(a and b) and (a == b or SequenceMatcher(None, a, b, autojunk=False).ratio() >= limit)


def remembered(memory: list[dict], title: str, question: str) -> dict | None:
    """La respuesta guardada a esta pregunta de una regla con este título (la más reciente), o None."""
    for item in reversed(memory):
        if _similar(item["question"], question, QUESTION_MATCH) and _similar(item["title"], title, TITLE_MATCH):
            return item
    return None


def answer_text(answer: str) -> str:
    """'si' y 'no' se escriben Sí y No; una respuesta escrita por el equipo va tal cual, sin el punto final."""
    return ANSWERS.get(answer) or answer.strip().rstrip(".")


def note(question: str, answer: str) -> str:
    """Lo que se agrega a la descripción: la pregunta y su respuesta."""
    return f"Aclaración del equipo: {question.strip()} {answer_text(answer)}."


def with_note(description: str, question: str, answer: str) -> str:
    """La descripción con la aclaración al final, sin pasarse del largo permitido (se recorta la pregunta, no la regla)."""
    extra = note(question, answer)
    room = reglas.MAX_TEXT - len(description) - 1
    if room < len(extra):
        keep = room - len(note("…", answer)) + 1
        if keep < 10:
            return description
        extra = note(question.strip()[:keep].rstrip() + "…", answer)
    return f"{description} {extra}".strip()


def _semantic(memory: list[dict], pending: list[tuple[str, str]], embed: Embed) -> list[dict | None]:
    """La respuesta recordada de cada (título, pregunta) pendiente según el significado, o None. Una sola llamada a embed."""
    texts = [m["question"] for m in memory] + [m["title"] for m in memory] + [q for _, q in pending] + [t for t, _ in pending]
    vectors = embed(texts)
    n, k = len(memory), len(pending)
    mem_q, mem_t, new_q, new_t = vectors[:n], vectors[n : 2 * n], vectors[2 * n : 2 * n + k], vectors[2 * n + k :]
    out: list[dict | None] = []
    for i in range(k):
        best, best_score = None, 0.0
        for j in range(n):
            question, title = float(new_q[i] @ mem_q[j]), float(new_t[i] @ mem_t[j])
            if question >= SEMANTIC_QUESTION and title >= SEMANTIC_TITLE and question > best_score:
                best, best_score = memory[j], question
        out.append(best)
    return out


def apply(text: str, memory: list[dict], embed: Embed | None = None) -> tuple[str, list[str]]:
    """
    El texto con las dudas que el equipo ya contestó resueltas (la aclaración va en la descripción) y los avisos de lo que
    se contestó solo («RN-003: ya respondiste «…»: Sí»). Sin cambios si no hay nada que contestar. `embed` permite reconocer
    la misma pregunta redactada distinto; si falla, se sigue solo con el texto.
    """
    if not memory:
        return text, []
    rules = reglas.parse(text).rules
    found: dict[tuple[str, str], dict] = {}
    pending: list[tuple[str, str, str]] = []
    for rule in rules:
        for doubt in rule.doubts:
            match = remembered(memory, rule.title, doubt)
            if match is not None:
                found[(rule.id, doubt)] = match
            else:
                pending.append((rule.id, rule.title, doubt))
    if pending and embed is not None:
        try:
            for (rid, _, doubt), match in zip(pending, _semantic(memory, [(t, d) for _, t, d in pending], embed), strict=True):
                if match is not None:
                    found[(rid, doubt)] = match
        except Exception:
            log.warning("No se pudieron comparar las dudas por significado; se usó solo el texto", exc_info=True)
    messages: list[str] = []
    for rule in rules:
        open_doubts, description = [], rule.description
        for doubt in rule.doubts:
            match = found.get((rule.id, doubt))
            if match is None:
                open_doubts.append(doubt)
                continue
            description = with_note(description, doubt, match["answer"])
            messages.append(f"{rule.id}: ya respondiste «{doubt}»: {answer_text(match['answer'])}")
        if len(open_doubts) != len(rule.doubts):
            text = reglas.set_fields(text, rule.id, {"descripcion": description, "dudas": open_doubts})
    return text, messages
