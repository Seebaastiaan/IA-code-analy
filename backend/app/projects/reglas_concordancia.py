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


def confidence(level: str | None, strength: str | None, crosscheck: str | None = None) -> str | None:
    """
    Solidez del resultado: la del nivel de verificación, ajustada por dos comprobaciones de su prueba.

    - Prueba de fuerza: «fuerte» (mató todos los cambios) sube un escalón; «débil» (no notó ninguno) la deja como mucho en «baja».
    - Segunda opinión (la IA lee el código sin ver la prueba): «coincide» sube un escalón; «discrepa» la deja como mucho en
      «baja», porque una de las dos está equivocada y no se sabe cuál.
    """
    if not level:
        return None
    base = CONFIDENCE.get(level)
    if base is None or level == "patron" or base == "ninguna":
        return base
    i = LADDER.index(base)
    if strength == "fuerte":
        i += 1
    if crosscheck == "coincide":
        i += 1
    i = min(i, 3)
    if strength == "debil" or crosscheck == "discrepa":
        i = min(i, 1)
    return LADDER[i]


def build(
    rules: list[tuple[str, str]], expected: dict[str, str], results: dict[str, tuple[str, str]], strength: dict[str, str] | None = None,
    crosscheck: dict[str, str] | None = None,
) -> list[Item]:
    """
    `rules` = (id, título) en orden; `results` = regla → (estado, nivel) del último análisis; `strength` = regla → resultado
    de su prueba de fuerza; `crosscheck` = regla → coincide | discrepa (la prueba contra la lectura independiente del código).
    """
    items = []
    for rid, title in rules:
        status, level = results.get(rid, (None, None))
        items.append(Item(rid, title, expected.get(rid), status, outcome(expected.get(rid), status), confidence(level, (strength or {}).get(rid), (crosscheck or {}).get(rid))))
    return items
