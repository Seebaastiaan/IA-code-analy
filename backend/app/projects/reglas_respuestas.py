"""
Dudas de las reglas como preguntas de sí o no, con memoria (docs/PLAN_REGLAS_AUTOMATICO.md, paso 4).

Una duda («¿el límite incluye el valor exacto?») se contesta con Sí o No. La respuesta se anota en la descripción de la
regla (así queda en el documento y la lee la IA que escribe la prueba) y se guarda en la memoria del proyecto: si una
importación nueva trae la misma pregunta de la misma regla, se contesta sola y no se vuelve a preguntar.
Las preguntas se reconocen por su texto (sin acentos ni signos, tolerando pequeñas diferencias de redacción de la IA).
"""

import hashlib
from difflib import SequenceMatcher

from app.analyses import reglas
from app.projects.reglas_importar import _fold

ANSWERS = {"si": "Sí", "no": "No"}
# Qué tan parecida debe ser una pregunta (y el título de su regla) para darla por la misma
QUESTION_MATCH = 0.8
TITLE_MATCH = 0.6


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


def note(question: str, answer: str) -> str:
    """Lo que se agrega a la descripción: la pregunta y su respuesta."""
    return f"Aclaración del equipo: {question.strip()} {ANSWERS[answer]}."


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


def apply(text: str, memory: list[dict]) -> tuple[str, list[str]]:
    """
    El texto con las dudas que el equipo ya contestó resueltas (la aclaración va en la descripción) y los avisos de lo que
    se contestó solo («RN-003: ya respondiste «…»: Sí»). Sin cambios si no hay nada que contestar.
    """
    if not memory:
        return text, []
    messages: list[str] = []
    for rule in reglas.parse(text).rules:
        open_doubts, description = [], rule.description
        for doubt in rule.doubts:
            found = remembered(memory, rule.title, doubt)
            if found is None:
                open_doubts.append(doubt)
                continue
            description = with_note(description, doubt, found["answer"])
            messages.append(f"{rule.id}: ya respondiste «{doubt}»: {ANSWERS[found['answer']]}")
        if len(open_doubts) != len(rule.doubts):
            text = reglas.set_fields(text, rule.id, {"descripcion": description, "dudas": open_doubts})
    return text, messages
