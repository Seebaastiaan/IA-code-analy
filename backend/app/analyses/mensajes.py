"""
Mensajes de los hallazgos en español.

Ruff y Bandit escriben sus mensajes en inglés. Aquí se traducen los de las reglas que la app revisa (Ruff:
E4, E7, E9, F, B, SIM, C4; Bandit: todas las pruebas con su código). Lo que cambia entre apariciones (el nombre de
la variable, del módulo, de la función) se conserva tal cual. Si un mensaje no está en el catálogo, se deja el
original: no se pierde información.
"""

import re

from app.analyses import familias

# Ruff: (patrón del mensaje en inglés, plantilla en español con \1, \2… de los grupos del patrón)
RUFF_PATTERNS: list[tuple[str, str]] = [
    (r"Import block is un-sorted or un-formatted", "Los imports no están ordenados"),
    (r"Use `enumerate\(\)` for index variable `(.+)` in `for` loop", r"Usa `enumerate()` para el índice `\1` del `for`"),
    (r"Missing required import: `(.+)`", r"Falta el import obligatorio `\1`"),
    (r"Line too long \((\d+) > (\d+)\)", r"Línea demasiado larga (\1 caracteres; el máximo es \2)"),
    (r"Trailing whitespace", "Espacios al final de la línea"),
    (r"Blank line contains whitespace", "La línea en blanco tiene espacios"),
    (r"No newline at end of file", "Falta el salto de línea al final del archivo"),
    (r"Use `(.+)` instead of `(.+)` for type annotation", r"Usa `\1` en lugar de `\2` en la anotación de tipo"),
    (r"Use `X \| Y` for type annotations", "Usa `X | Y` en las anotaciones de tipo"),
    (r"Use `X \| None` for type annotations", "Usa `X | None` en las anotaciones de tipo"),
    (r"Import from `(.+)` instead: (.+)", r"Importa \2 desde `\1`"),
    (r"Unnecessary open mode parameters", "El modo de `open` sobra (\"r\" es el de siempre)"),
    (r"Use f-string instead of `format` call", "Usa un f-string en lugar de `format`"),
    (r"Use `super\(\)` instead of `super\(__class__, self\)`", "Usa `super()` sin argumentos"),
    (r"Class `(.+)` inherits from `object`", r"La clase `\1` hereda de `object` sin necesidad"),
    (r"`(.+)` imported but unused; consider using `importlib.util.find_spec` to test for availability", r"`\1` se importa y no se usa; si es para comprobar que existe, usa `importlib.util.find_spec`"),
    (r"`(.+)` imported but unused; consider removing, adding to `__all__`, or using a redundant alias", r"`\1` se importa y no se usa; bórralo, agrégalo a `__all__` o usa un alias redundante"),
    (r"`(.+)` imported but unused", r"`\1` se importa y no se usa"),
    (r"`from (.+) import \*` used; unable to detect undefined names", r"`from \1 import *` impide saber qué nombres no están definidos"),
    (r"`(.+)` may be undefined, or defined from star imports", r"`\1` puede no estar definido o venir de un `import *`"),
    (r"f-string without any placeholders", "f-string sin ningún `{}`: no interpola nada"),
    (r"Dictionary key literal `(.+)` repeated", r"La clave `\1` está repetida en el diccionario"),
    (r"Use `==` to compare constant literals.*", "Usa `==` para comparar con literales, no `is`"),
    (r"Redefinition of unused `(.+)` from line (\d+)", r"Se redefine `\1` (ya definido en la línea \2) sin haberse usado"),
    (r"Undefined name `(.+)`", r"El nombre `\1` no está definido"),
    (r"Local variable `(.+)` referenced before assignment", r"La variable local `\1` se usa antes de asignarla"),
    (r"Local variable `(.+)` is assigned to but never used", r"La variable local `\1` se asigna pero nunca se usa"),
    (r"Annotated local variable `(.+)` is never used", r"La variable anotada `\1` nunca se usa"),
    (r"Multiple imports on one line", "Varios imports en una sola línea"),
    (r"Module level import not at top of file", "Import que no está al inicio del archivo"),
    (r"Multiple statements on one line \(colon\)", "Varias sentencias en una línea (con dos puntos)"),
    (r"Multiple statements on one line \(semicolon\)", "Varias sentencias en una línea (con punto y coma)"),
    (r"Statement ends with an unnecessary semicolon", "La sentencia termina con un punto y coma que sobra"),
    (r"Comparison to `None` should be `cond is None`", "Comparar con `None` debe hacerse con `is None`"),
    (r"Comparison to `None` should be `cond is not None`", "Comparar con `None` debe hacerse con `is not None`"),
    (r"Avoid equality comparisons to `(True|False)`; use `(.+)` for truth checks", r"No compares con `\1` usando `==`; usa `\2`"),
    (r"Avoid equality comparisons to `(True|False)`; use `(.+)` for false checks", r"No compares con `\1` usando `==`; usa `\2`"),
    (r"Test for membership should be `not in`", "La comprobación de pertenencia debe ser `not in`"),
    (r"Test for object identity should be `is not`", "La comprobación de identidad debe ser `is not`"),
    (r"Use `is` and `is not` for type comparisons, or `isinstance\(\)` for isinstance checks", "Para comparar tipos usa `is`/`is not` o `isinstance()`"),
    (r"Do not assign a `lambda` expression, use a `def`", "No asignes una `lambda` a una variable: usa `def`"),
    (r"Ambiguous variable name: `(.+)`", r"Nombre de variable ambiguo: `\1`"),
    (r"Ambiguous class name: `(.+)`", r"Nombre de clase ambiguo: `\1`"),
    (r"Ambiguous function name: `(.+)`", r"Nombre de función ambiguo: `\1`"),
    (r"Do not use bare `except`", "No uses `except:` sin indicar la excepción"),
    (r"SyntaxError: (.+)", r"Error de sintaxis: \1"),
    (r"Failed to parse .*", "No se pudo leer el archivo (error de sintaxis)"),
    (r"Unary prefix increment and decrement operators are not supported", "Python no tiene `++` ni `--`"),
    (r"Do not mutate `os\.environ`.*|Do not assign to `os\.environ`.*", "No asignes `os.environ` directamente"),
    (r"Using `hasattr\(x, `__call__`\)` to test if x is callable is unreliable.*", "`hasattr(x, \"__call__\")` no es confiable: usa `callable(x)`"),
    (r"Using the characters `(.+)` as strip.*|Using `.*strip\(.*\)` with multi-character strings is misleading", "`strip` con varios caracteres quita cada carácter por separado, no la cadena completa"),
    (r"Do not use mutable data structures for argument defaults", "No uses una lista, dict o set como valor por defecto de un argumento"),
    (r"Loop control variable `(.+)` not used within loop body", r"La variable del ciclo `\1` no se usa dentro del ciclo"),
    (r"Do not perform function call `(.+)` in argument defaults.*", r"No llames a `\1` en el valor por defecto de un argumento"),
    (r"Do not call `getattr` with a constant attribute value.*", "No uses `getattr` con un nombre fijo: escribe el atributo directo"),
    (r"Do not call `setattr` with a constant attribute value.*", "No uses `setattr` con un nombre fijo: asigna el atributo directo"),
    (r"Do not `assert False`.*", "No uses `assert False`: lanza `AssertionError`"),
    (r"`return` inside `finally` blocks cause exceptions to be silenced", "Un `return` dentro de `finally` silencia las excepciones"),
    (r"`break` inside `finally` blocks cause exceptions to be silenced", "Un `break` dentro de `finally` silencia las excepciones"),
    (r"`continue` inside `finally` blocks cause exceptions to be silenced", "Un `continue` dentro de `finally` silencia las excepciones"),
    (r"Found useless comparison.*|Pointless comparison.*", "Comparación inútil: su resultado no se usa"),
    (r"Found useless expression.*", "Expresión inútil: su resultado no se usa"),
    (r"`pytest\.raises\((.+)\)` is too broad.*", r"`pytest.raises(\1)` es demasiado amplio: indica la excepción concreta"),
    (r"Use of `functools\.lru_cache` or `functools\.cache` on methods can lead to memory leaks", "`lru_cache` o `cache` en un método puede causar fugas de memoria"),
    (r"Loop control variable `(.+)` overrides iterable it iterates", r"La variable del ciclo `\1` pisa el iterable que recorre"),
    (r"Function definition does not bind loop variable `(.+)`", r"La función no fija la variable del ciclo `\1`: usará siempre su último valor"),
    (r"`(.+)` is an abstract base class, but it has no abstract methods.*", r"`\1` es una clase abstracta sin métodos abstractos"),
    (r"Star-arg unpacking after a keyword argument is strongly discouraged", "Desempaquetar `*args` después de un argumento con nombre se desaconseja"),
    (r"`(.+)` is an empty method in an abstract base class, but has no abstract decorator", r"`\1` es un método vacío de una clase abstracta sin `@abstractmethod`"),
    (r"No explicit `stacklevel` keyword argument found", "Falta `stacklevel` en `warnings.warn`"),
    (r"Within an `except` clause, raise exceptions with `raise \.\.\. from err` or `raise \.\.\. from None`.*", "Dentro de un `except`, usa `raise ... from err` o `raise ... from None`"),
    (r"`zip\(\)` without an explicit `strict=` parameter", "`zip()` sin el parámetro `strict=`"),
    (r"Do not use `(.+)` with a trailing comma.*", r"Coma final innecesaria en `\1`"),
    (r"Use `(.+)` instead of `(.+)`", r"Usa `\1` en lugar de `\2`"),
    (r"Use a single `if` statement instead of nested `if` statements", "Usa un solo `if` en lugar de `if` anidados"),
    (r"Use a single `with` statement with multiple contexts instead of nested `with` statements", "Usa un solo `with` con varios contextos en lugar de `with` anidados"),
    (r"Return the condition `(.+)` directly", r"Devuelve la condición `\1` directamente"),
    (r"Use `contextlib\.suppress\((.+)\)` instead of `try`-`except`-`pass`", r"Usa `contextlib.suppress(\1)` en lugar de `try`-`except`-`pass`"),
    (r"Use ternary operator `(.+)` instead of `if`-`else`-block", r"Usa el operador ternario `\1` en lugar del bloque `if`-`else`"),
    (r"Use `(.+)` instead of `for` loop", r"Usa `\1` en lugar del ciclo `for`"),
    (r"Use a context manager for opening files", "Abre el archivo con un `with` (administrador de contexto)"),
    (r"Use `(.+) in (.+)` instead of `(.+) in (.+)\.keys\(\)`", r"Usa `\1 in \2` en lugar de `\3 in \4.keys()`"),
    (r"Use `(.+) != (.+)` instead of `not (.+) == (.+)`", r"Usa `\1 != \2` en lugar de `not \3 == \4`"),
    (r"Use `bool\((.+)\)` instead of `True if (.+) else False`", r"Usa `bool(\1)` en lugar de `True if \2 else False`"),
    (r"Yoda condition detected.*|Yoda condition.*", "Condición «Yoda»: escribe primero la variable y luego el valor"),
    (r"Use `(.+)` instead of an `if` block", r"Usa `\1` en lugar de un bloque `if`"),
    (r"Use `(.+)` instead of `(.+)\.get\((.+), None\)`", r"Usa `\1` en lugar de `\2.get(\3, None)`"),
    (r"Use `(.+)` instead of `(.+)`.*", r"Usa `\1` en lugar de `\2`"),
    (r"Unnecessary `(list|set|dict|tuple)` (call|comprehension)(.*)", r"`\1` innecesario: se puede escribir directamente como literal o comprensión"),
    (r"Unnecessary (.+) \(rewrite as a (.+)\)", r"\1 innecesario (escríbelo como \2)"),
    (r"Unnecessary (.+)", r"Innecesario: \1"),
    (r"Do not use `(.+)`.*", r"No uses `\1`"),
    (r"Too many .*", "Demasiados elementos: simplifica"),
]

# Bandit: código de la prueba → mensaje en español (los datos variables, como un valor, se agregan aparte)
BANDIT_MESSAGES: dict[str, str] = {
    "B101": "Se usa `assert`: el código se elimina al compilar con optimización",
    "B102": "Se usa `exec`: ejecuta como código cualquier texto",
    "B103": "Permisos de archivo demasiado abiertos",
    "B104": "Posible enlace a todas las interfaces de red (0.0.0.0)",
    "B105": "Posible contraseña escrita en el código",
    "B106": "Posible contraseña escrita en el código (argumento)",
    "B107": "Posible contraseña escrita en el código (valor por defecto)",
    "B108": "Uso probablemente inseguro de un archivo o carpeta temporal",
    "B110": "`try`/`except`/`pass`: el error se oculta sin registrarlo",
    "B112": "`try`/`except`/`continue`: el error se salta sin registrarlo",
    "B113": "Petición HTTP sin `timeout`: puede quedarse esperando para siempre",
    "B201": "Flask con `debug=True`: permite ejecutar código desde el navegador",
    "B202": "`tarfile.extractall` sin validar los archivos del paquete",
    "B301": "`pickle` puede ejecutar código al leer datos no confiables",
    "B302": "`marshal` no es seguro con datos externos",
    "B303": "Uso de un hash inseguro (MD5 o SHA1)",
    "B304": "Uso de un cifrado inseguro",
    "B305": "Uso del modo de cifrado ECB, que revela patrones",
    "B306": "`tempfile.mktemp` es inseguro: otro proceso puede ocupar el nombre",
    "B307": "Uso de `eval`: ejecuta como código cualquier texto",
    "B308": "`mark_safe` desactiva el escape de HTML",
    "B310": "`urlopen` acepta esquemas como `file://`: valida la URL",
    "B311": "El módulo `random` es predecible: no sirve para seguridad",
    "B312": "Telnet no cifra la comunicación",
    "B321": "FTP no cifra la comunicación",
    "B323": "Contexto SSL sin verificación de certificados",
    "B324": "Uso de un hash inseguro (MD5 o SHA1)",
    "B401": "Se importa `telnetlib`: Telnet no cifra la comunicación",
    "B403": "Se importa `pickle`: es inseguro con datos no confiables",
    "B404": "Se importa `subprocess`: ejecutar comandos del sistema es un riesgo",
    "B405": "Se importa `xml.etree`: es vulnerable a XML maliciosos",
    "B406": "Se importa `xml.sax`: es vulnerable a XML maliciosos",
    "B407": "Se importa `xml.expat`: es vulnerable a XML maliciosos",
    "B408": "Se importa `xml.dom.minidom`: es vulnerable a XML maliciosos",
    "B410": "Se importa `lxml`: resuelve entidades externas por defecto",
    "B413": "Se importa `pycrypto`: ya no se mantiene",
    "B501": "Petición con `verify=False`: no valida el certificado",
    "B502": "Versión insegura de SSL/TLS",
    "B503": "Versión insegura de SSL/TLS",
    "B504": "SSL sin versión explícita: puede negociarse un protocolo inseguro",
    "B505": "Clave criptográfica demasiado corta",
    "B506": "`yaml.load` puede ejecutar código: usa `yaml.safe_load`",
    "B507": "Se aceptan claves de host SSH desconocidas",
    "B601": "Posible inyección de comandos en una llamada a la shell (paramiko)",
    "B602": "Se lanza un proceso con `shell=True`: posible inyección de comandos",
    "B603": "Se lanza un proceso sin `shell=True`: revisa que los argumentos sean de confianza",
    "B604": "Función con `shell=True`: posible inyección de comandos",
    "B605": "Se lanza un proceso desde la shell: posible inyección de comandos",
    "B606": "Se lanza un proceso sin shell: revisa que los argumentos sean de confianza",
    "B607": "Se lanza un proceso con una ruta parcial del ejecutable",
    "B608": "Posible inyección SQL: la consulta se arma con texto",
    "B609": "Comodín `*` en un comando del sistema: posible inyección",
    "B610": "Posible inyección SQL con `QuerySet.extra` de Django",
    "B611": "Posible inyección SQL con `RawSQL` de Django",
    "B612": "`logging.config.listen` acepta configuración por red",
    "B613": "Caracteres Unicode bidireccionales en el código",
    "B614": "`torch.load` usa pickle: un modelo descargado puede ejecutar código",
    "B615": "Descarga de Hugging Face sin fijar la versión",
    "B701": "Jinja2 con `autoescape` desactivado: posible XSS",
    "B702": "Mako sin escape de HTML: posible XSS",
    "B703": "`mark_safe` de Django desactiva el escape de HTML",
    "B704": "`Markup` con datos del usuario: posible XSS",
}

_COMPILED = [(re.compile(f"^(?:{p})$", re.DOTALL), r) for p, r in RUFF_PATTERNS]
# El dato entre comillas de B105/B106/B107 («Possible hardcoded password: 'x'»)
_PASSWORD_VALUE = re.compile(r": (['\"].*['\"])\s*$", re.DOTALL)


def ruff_message(message: str, code: str | None = None) -> str:
    """
    Mensaje de Ruff en español. Si no está en el catálogo y sigue en inglés, el de la familia de la regla (`code`):
    nunca se muestra el texto en inglés.
    """
    text = message.strip()
    for pattern, template in _COMPILED:
        match = pattern.match(text)
        if match:
            return pattern.sub(template, text)
    if code and familias.english(text):
        return familias.family(code)[0]
    return message


def bandit_message(code: str, message: str) -> str:
    """Mensaje de Bandit en español; si no está en el catálogo, el original."""
    spanish = BANDIT_MESSAGES.get(code)
    if not spanish:
        return message
    if code in {"B105", "B106", "B107"}:
        value = _PASSWORD_VALUE.search(message)
        if value:
            return f"{spanish}: {value.group(1)}"
    return spanish
