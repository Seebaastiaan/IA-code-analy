"""
Ruff y Bandit en español para lo que no está en el catálogo (app.analyses.mensajes y app.analyses.remedies).

Un repo puede traer su propia configuración de Ruff y activar reglas que IA voy no revisa por su cuenta (I001 de isort,
UP de pyupgrade, E501…). Antes esas salían con el mensaje en inglés y con el ejemplo genérico de la documentación de Ruff
(«import numpy as np / import pandas»), que no tiene nada que ver con el código del usuario. Aquí cada familia de reglas
tiene una explicación en español, y `localize` corrige también los hallazgos ya guardados en análisis anteriores.
"""

import re

# Prefijo de la regla → (qué pasa, por qué importa, qué hacer). Se busca el prefijo más largo.
RUFF_FAMILIES: dict[str, tuple[str, str, str]] = {
    "I": ("Los imports no están ordenados", "Los imports desordenados hacen difícil ver de qué depende el archivo y causan conflictos al juntar ramas.",
          "Ordénalos en tres grupos separados por una línea en blanco (biblioteca estándar, paquetes instalados y módulos del proyecto), cada uno en orden alfabético."),
    "UP": ("Sintaxis de una versión antigua de Python", "Hay una forma más nueva y simple de escribir esto en la versión de Python que usa el proyecto.",
           "Usa la forma moderna; la corrección automática suele hacerlo sola."),
    "E": ("Problema de formato del código", "El formato inconsistente hace el código más difícil de leer y revisar.", "Ajusta el formato de esa línea como indica la regla."),
    "W": ("Problema de espacios o formato", "Los espacios sobrantes o faltantes ensucian los cambios en git y dificultan la revisión.", "Corrige los espacios de esa línea."),
    "N": ("Nombre que no sigue la convención de Python", "Los nombres fuera de convención confunden: clases en CamelCase, funciones y variables en minúsculas_con_guiones.",
          "Renombra siguiendo la convención (PEP 8)."),
    "D": ("Documentación (docstring) faltante o con formato incorrecto", "La documentación ayuda a entender qué hace cada función sin leer todo su código.",
          "Agrega o corrige el docstring de esa función, clase o módulo."),
    "ANN": ("Falta la anotación de tipo", "Sin tipos, el editor y las herramientas no pueden avisar de errores al usar la función.", "Agrega los tipos de los argumentos y del valor de retorno."),
    "S": ("Posible problema de seguridad", "Este patrón puede abrir una vulnerabilidad si llegan datos del usuario.", "Revisa la línea y usa la alternativa segura."),
    "PL": ("El código se puede simplificar o tiene un error común", "Es un patrón que suele esconder errores o complicar el código.", "Reescríbelo de forma más directa."),
    "RUF": ("Patrón poco claro o propenso a errores", "Puede comportarse distinto de lo que parece.", "Reescríbelo de forma explícita."),
    "PERF": ("Código más lento de lo necesario", "Hay una forma más rápida de hacer lo mismo.", "Usa la alternativa más eficiente (por ejemplo, una comprensión en lugar de un ciclo con append)."),
    "PT": ("Estilo de las pruebas de pytest", "Las pruebas con un estilo uniforme son más fáciles de leer y mantener.", "Ajusta la prueba al estilo recomendado de pytest."),
    "RET": ("El `return` se puede simplificar", "Un `return` innecesario o inconsistente hace más difícil seguir la función.", "Simplifica los `return` de la función."),
    "ARG": ("Argumento que no se usa", "Un argumento sin usar confunde a quien llama la función.", "Quítalo o úsalo; si es obligatorio por la firma, llámalo con `_`."),
    "ERA": ("Código comentado", "El código comentado se queda desactualizado y confunde; git ya guarda el historial.", "Bórralo."),
    "T20": ("`print` olvidado", "Los `print` de depuración ensucian la salida en producción.", "Quítalo o usa `logging`."),
    "DTZ": ("Fecha sin zona horaria", "Una fecha sin zona horaria se interpreta distinto según el servidor.", "Indica la zona horaria (por ejemplo `datetime.now(tz=...)`)."),
    "EM": ("Mensaje de error escrito dentro de la excepción", "Escribir el texto directamente en `raise` lo duplica en el traceback.", "Guarda el mensaje en una variable y pásala a la excepción."),
    "G": ("Formato del mensaje de logging", "Formatear el texto antes de llamar a logging lo hace aunque el mensaje no se registre.", "Pasa los valores como argumentos: `log.info(\"x=%s\", x)`."),
    "TRY": ("Manejo de excepciones mejorable", "Una excepción mal manejada puede ocultar el error real.", "Captura la excepción concreta y conserva la original (`raise ... from e`)."),
    "BLE": ("Se captura cualquier excepción", "`except Exception` oculta errores que no esperabas.", "Captura solo las excepciones que sabes manejar."),
    "A": ("Nombre que oculta una función de Python", "Usar nombres como `list`, `id` o `type` tapa la función original.", "Renombra la variable."),
    "PTH": ("Manejo de rutas con `os.path`", "`pathlib` es más claro y funciona igual en Windows y Linux.", "Usa `pathlib.Path`."),
    "C90": ("Función demasiado compleja", "Una función con muchos caminos es difícil de probar y de entender.", "Divídela en funciones más pequeñas."),
    "F": ("Error de nombres o imports", "Puede fallar al ejecutarse o dejar código muerto.", "Corrige el nombre o el import señalado."),
    "B": ("Patrón propenso a errores", "Este código suele comportarse distinto de lo que parece.", "Reescríbelo como indica la regla."),
    "SIM": ("El código se puede escribir de forma más simple", "Una versión más simple es más fácil de leer y de mantener.", "Simplifícalo."),
    "C4": ("La comprensión o la llamada a `list()`/`dict()`/`set()` sobra", "Hace lo mismo con más pasos.", "Reescríbela como literal o comprensión directa."),
}
DEFAULT = ("Problema de estilo o de calidad del código", "Hace el código más difícil de leer o mantener.", "Corrige la línea señalada.")

# Palabras que delatan un texto en inglés (fuera de lo que va entre comillas invertidas)
_ENGLISH = re.compile(
    r"\b(the|is|are|use|used|using|instead|of|detected|found|should|missing|unsorted|un-sorted|import block|line too long|"
    r"trailing|whitespace|blank|unnecessary|consider|replace|remove|organize|avoid|possible|unused|call|prefer)\b",
    re.IGNORECASE,
)
_SPANISH = re.compile(r"[áéíóúñ¿¡]|\b(se|no|del|una|el|los|las|que|usa|para)\b", re.IGNORECASE)
_CODE = re.compile(r"`[^`]*`")
_AUTO_FIX = re.compile(r"\s*Corrección automática: ([^\n]*?)\.?$")
AUTO_FIX_ES = " Tiene corrección automática: «Aplicar corrección automática» lo hace por ti."


def english(text: str) -> bool:
    plain = _CODE.sub("", text or "")
    return bool(_ENGLISH.search(plain)) and not _SPANISH.search(plain)


def family(code: str) -> tuple[str, str, str]:
    # «PLR2004» es de PL (pylint) aunque detrás venga una letra; «SIM105» no es de S, ni «ERA001» de E
    prefix = max((p for p in RUFF_FAMILIES if code.startswith(p) and re.match(r"[A-Z]?\d", code[len(p):])), key=len, default=None)
    return RUFF_FAMILIES[prefix] if prefix else DEFAULT


def auto_fix_note(rec: str) -> str:
    """La nota de la corrección automática en español (Ruff la escribe en inglés: «Organize imports»)."""
    match = _AUTO_FIX.search(rec or "")
    if match and english(match.group(1)):
        return rec[: match.start()] + AUTO_FIX_ES
    return rec
