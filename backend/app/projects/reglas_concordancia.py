"""
Casos de control y concordancia (docs/PLAN_REGLAS_AUTOMATICO.md, paso 6).

El equipo puede marcar, de las reglas que conoce, si **se cumple** o **se viola** en su código. Eso no cambia ningún
resultado: solo sirve para medir al programa («acertó 11 de 12 reglas que conocían») contra el último análisis.
"""

from dataclasses import dataclass

EXPECTED = ("cumple", "viola")
# Estados del análisis que dicen «se viola»
VIOLATED = {"no_cumple", "no_implementada"}
# Con qué solidez se comprobó cada regla (de qué nivel de verificación salió su resultado)
CONFIDENCE = {"pruebas_y_patron": "alta", "pruebas": "media", "patron": "baja", "ninguno": "ninguna"}


@dataclass
class Item:
    rule_id: str
    title: str
    expected: str | None
    # Estado de la regla en el último análisis (None = no se ha analizado)
    status: str | None
    # acerto | fallo | sin_resultado | None (sin caso de control)
    outcome: str | None
    confidence: str | None


def outcome(expected: str | None, status: str | None) -> str | None:
    """Si el resultado del análisis coincide con lo que el equipo sabe de la regla."""
    if expected is None:
        return None
    if status == "cumple":
        return "acerto" if expected == "cumple" else "fallo"
    if status in VIOLATED:
        return "acerto" if expected == "viola" else "fallo"
    # sin verificar, prueba rota o fuera del código: el programa no se pronunció
    return "sin_resultado"


LADDER = ("ninguna", "baja", "media", "alta")


def confidence(level: str | None, strength: str | None) -> str | None:
    """
    Solidez del resultado: la del nivel de verificación, ajustada por la prueba de fuerza de su prueba: «fuerte» (mató todos
    los cambios) sube un escalón; «débil» (no notó ninguno) la deja como mucho en «baja».
    """
    if not level:
        return None
    base = CONFIDENCE.get(level)
    if base is None or level == "patron" or strength is None or base == "ninguna":
        return base
    i = LADDER.index(base)
    if strength == "fuerte":
        return LADDER[min(i + 1, 3)]
    if strength == "debil":
        return LADDER[min(i, 1)]
    return base


def build(
    rules: list[tuple[str, str]], expected: dict[str, str], results: dict[str, tuple[str, str]], strength: dict[str, str] | None = None,
) -> list[Item]:
    """`rules` = (id, título) en orden; `results` = regla → (estado, nivel) del último análisis; `strength` = regla → resultado de su prueba de fuerza."""
    items = []
    for rid, title in rules:
        status, level = results.get(rid, (None, None))
        items.append(Item(rid, title, expected.get(rid), status, outcome(expected.get(rid), status), confidence(level, (strength or {}).get(rid))))
    return items
