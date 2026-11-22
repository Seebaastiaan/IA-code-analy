"""
Reglas de negocio del proyecto analizado (docs/adr/ADR-003-reglas-de-negocio.md y
docs/PROPUESTA_REGLAS_NEGOCIO.md).

Cada proyecto declara sus reglas en `reglas_negocio.toml` (raíz del repo o `docs/`) y las liga a algo
verificable. Si el repo no lo tiene, o el suyo no es válido, se usan las cargadas en la app (Configuración o
Nuevo análisis); un archivo válido del repo siempre gana. Dos niveles, combinados en un estado por regla (`combine`):

- **Patrón** (`run`, en el backend): `prohibido` (regex que no debe aparecer) y `obligatorio` (regex que debe
  aparecer en cada archivo) sobre los `.py` de `rutas`. Como Bandit y Ruff, solo lee el código. Las pruebas
  no se revisan aquí: `prohibido` en una prueba es normal (la prueba lo usa para comprobar la regla).
- **Pruebas** (`with_tests`): las pruebas marcadas `@pytest.mark.regla("RN-002")` o llamadas `test_rn002_…`.
  En el sandbox las corre pytest con el plugin app.analysis.ia_voy_reglas; sin sandbox se encuentran leyendo
  las pruebas (`declared_tests`, con `ast`) y la regla queda "sin verificar" con el motivo.

Un `id` repetido invalida el archivo. Las reglas que se contradicen (una prohíbe lo que otra exige en las mismas
rutas) o que parecen duplicadas (mismo patrón y rutas, o mismo título o descripción) solo dan avisos (`conflicts`), al
validar y en el reporte; se siguen verificando todas.

Los resultados se guardan aparte de los hallazgos (app.analyses.reglas_store) y todavía no entran al score.
"""

import ast
import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Literal

from app.analyses.analyzers import is_test_path
from app.analyses.workspace import is_excluded

FILENAME = "reglas_negocio.toml"
# Dónde se busca, en orden
LOCATIONS = (FILENAME, f"docs/{FILENAME}")
MAX_BYTES = 256 * 1024
MAX_RULES = 200
MAX_TITLE = 120
MAX_TEXT = 2000
MAX_PATHS = 50
MAX_PATTERN = 500
# Evidencia guardada por regla (el total se cuenta completo)
MAX_EVIDENCE = 20
# Líneas más largas que esto (código minificado, datos) no se revisan con los patrones
MAX_LINE = 2000
# Pruebas guardadas por regla y avisos por análisis
MAX_TESTS = 20
MAX_WARNINGS = 20
# Archivos de prueba más grandes que esto no se leen buscando marcadores
MAX_TEST_FILE = 1024 * 1024

ID_RE = re.compile(r"^RN-\d{3}$")
# Marca del importador: dos reglas que el documento contradice (no se puede usar el archivo con las dos)
MARKED_CONTRADICTION = re.compile(r"^\s*#\s*CONTRADICCI[OÓ]N\s+(RN-\d{3})\s+(?:y\s+)?(RN-\d{3})\s*:?\s*(.*)$", re.IGNORECASE)
# Nombre alternativo al marcador: test_rn002_… (mismo criterio que el plugin ia_voy_reglas)
TEST_NAME_RE = re.compile(r"^test_rn(\d{3})(?:_|$)", re.IGNORECASE)
SEVERITIES = ("alta", "media", "baja")
REQUIRED = ("id", "titulo", "descripcion", "severidad")
OPTIONAL_TEXT = ("historia", "responsable", "criterio")
# Formato v2 (docs/PROPUESTA_REGLAS_VERIFICABLES.md §5): todos opcionales, un archivo v1 sigue siendo válido
TYPES = ("datos", "flujo", "calculo", "permisos", "auditoria", "integracion", "proceso")
STATES = ("borrador", "aprobada")
V2_FIELDS = {"tipo", "estado", "fuente", "dudas", "escenario"}
RULE_FIELDS = {*REQUIRED, *OPTIONAL_TEXT, "rutas", "prohibido", "obligatorio", "ia", *V2_FIELDS}
PROJECT_FIELDS = {"nombre", "version", "formato"}
SCENARIO_FIELDS = ("dado", "cuando", "entonces")
MAX_SCENARIOS = 10
MAX_DOUBTS = 10
MAX_DOUBT = 300
# «Dado …, cuando …, entonces …» en un `criterio` v1: se lee como un escenario
CRITERION_RE = re.compile(r"^\s*dad[oa]s?\s+(?P<dado>.+?)\s*,\s*cuando\s+(?P<cuando>.+?)\s*,\s*entonces\s+(?P<entonces>.+?)\s*\.?\s*$", re.IGNORECASE | re.DOTALL)

# PROPUESTA_REGLAS_VERIFICABLES.md §9. prueba_rota = falló la prueba o su arnés, no el código (no se culpa al código);
# no_implementada = la acción del escenario no existe en el código; fuera_del_codigo = regla de proceso (no se verifica)
Status = Literal["cumple", "no_cumple", "prueba_rota", "no_implementada", "sin_verificar", "fuera_del_codigo"]
# Excepciones que cuentan como «el código no cumple»: un assert del *Entonces* o pytest.fail / pytest.raises
ASSERT_EXCEPTIONS = {"AssertionError", "Failed"}
Level = Literal["pruebas", "patron", "pruebas_y_patron", "ninguno"]
Origin = Literal["repo", "app"]
# Texto que ve el usuario como origen de las reglas cargadas en la app
APP_SOURCE = "Configuración (cargadas en la app)"


# Plantilla que se descarga desde Configuración → Reglas de negocio (formato v2, docs/PROPUESTA_REGLAS_VERIFICABLES.md §5)
TEMPLATE = '''# reglas_negocio.toml — reglas de negocio del proyecto (IA voy, docs/PROPUESTA_REGLAS_VERIFICABLES.md §5)
# Va en la raíz del repositorio (o en docs/) y se sube con commit, como el resto del código.
# Cada regla se verifica con una prueba (@pytest.mark.regla("RN-002") o test_rn002_…): IA voy la puede escribir a partir
# de sus escenarios. Solo cuentan las reglas con estado = "aprobada".

[proyecto]
nombre  = "Mi proyecto"
version = "1.0"
formato = 2

# Avanzado · patrón: para lo que se ve en el texto del código (`prohibido` no se genera solo)
[[regla]]
id          = "RN-001"                       # RN- + 3 dígitos, único
titulo      = "Montos con Decimal"
descripcion = "Todo monto de dinero se calcula con Decimal; nunca con float."
severidad   = "alta"                         # alta | media | baja
estado      = "aprobada"                     # borrador | aprobada (solo cuentan las aprobadas)
rutas       = ["app/pagos/"]                 # opcional · vacío = todo el repo
prohibido   = 'float\\('                      # opcional · regex que NO debe aparecer

[[regla]]
id          = "RN-002"
titulo      = "Un pedido cancelado no vuelve a pagado"
descripcion = "Una vez cancelado, el estado de un pedido no puede cambiar a 'pagado'."
severidad   = "alta"
tipo        = "flujo"                        # datos | flujo | calculo | permisos | auditoria | integracion | proceso
estado      = "aprobada"
fuente      = "Requisitos.docx · §3.2"       # opcional · de dónde sale la regla
historia    = "HU-01"                        # opcional · trazabilidad
dudas       = []                             # lo ambiguo del documento: con dudas no se aprueba desde la app

  [[regla.escenario]]                        # uno o más (máx. 10): la prueba sale de aquí
  dado     = "un pedido cancelado"
  cuando   = "se intenta marcar como pagado"
  entonces = "se rechaza y el pedido sigue cancelado"

[[regla]]
id          = "RN-003"
titulo      = "Solo administración borra usuarios"
descripcion = "Borrar un usuario lo puede hacer solo un administrador; los demás roles reciben 403."
severidad   = "media"
tipo        = "permisos"
estado      = "borrador"                     # todavía no cuenta: apruébala cuando esté lista
rutas       = ["app/admin/"]

  [[regla.escenario]]
  dado     = "un usuario con rol vendedor"
  cuando   = "intenta borrar otro usuario"
  entonces = "se rechaza con 403 y el usuario sigue existiendo"
'''


def _toml_str(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def code_folders(files: list[str]) -> list[str]:
    """Carpetas de primer nivel con código del proyecto (sin pruebas), las de más archivos primero."""
    count: dict[str, int] = {}
    for f in files:
        parts = PurePosixPath(f).parts
        if len(parts) > 1 and f.endswith(".py") and not is_test_path(f) and parts[0] != "docs":
            count[parts[0]] = count.get(parts[0], 0) + 1
    return sorted(count, key=lambda d: (-count[d], d))


def template_for(project: str, files: list[str]) -> str:
    """
    Plantilla de un proyecto: su nombre en [proyecto] y `rutas` de carpetas que existen en su repositorio
    (sin clonar todavía, o sin carpetas con código: todo el repo).
    """
    folders = code_folders(files)
    first = folders[0] if folders else None
    second = folders[1] if len(folders) > 1 else first
    rutas = lambda d: f'["{d}/"]' if d else "[]"
    return (
        TEMPLATE.replace("reglas de negocio del proyecto (", f"reglas de negocio de {project} (", 1)
        .replace('nombre  = "Mi proyecto"', f"nombre  = {_toml_str(project)}", 1)
        .replace('rutas       = ["app/pagos/"]                 #', f"rutas       = {rutas(first)}".ljust(46) + " #", 1)
        .replace('rutas       = ["app/admin/"]', f"rutas       = {rutas(second)}", 1)
    )


def missing_paths(ruleset: "RuleSet", files: list[str], project: str) -> list[str]:
    """Avisos de `rutas` que no corresponden a ningún archivo del proyecto (la regla no revisaría nada)."""
    return [
        f"{r.id}: la ruta `{p}` no existe en {project}"
        for r in ruleset.rules
        for p in r.paths
        if not any(is_excluded(f, [p]) for f in files)
    ][:MAX_WARNINGS]


# Caracteres con significado en una regex: un patrón sin ellos (o con ellos escapados) busca un texto fijo
_REGEX_META = frozenset(".^$*+?{}[]|()")


def _literal(pattern: str) -> str | None:
    """Texto fijo que busca `pattern` (p. ej. `@requiere_admin`, `os\\.getenv`); None si usa regex de verdad."""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "\\":
            # \d, \w, \b…: ya no es un texto fijo
            if i + 1 >= len(pattern) or pattern[i + 1].isalnum():
                return None
            out.append(pattern[i + 1])
            i += 2
            continue
        if c in _REGEX_META:
            return None
        out.append(c)
        i += 1
    return "".join(out) or None


def _overlap(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    """Las `rutas` de dos reglas comparten archivos (vacío = todo el repo)."""
    if not a or not b:
        return True
    return any(is_excluded(x.rstrip("/"), [y]) or is_excluded(y.rstrip("/"), [x]) for x in a for y in b)


def _norm(text: str) -> str:
    return " ".join(text.casefold().split()).rstrip(".;:")


def _forces_forbidden(forbidden: re.Pattern, required: str) -> bool:
    """Todo archivo que cumple `required` contiene `forbidden`: el mismo patrón, o `required` es un texto fijo que lo incluye."""
    if forbidden.pattern == required:
        return True
    lit = _literal(required)
    # Con espacios alrededor, como en una línea real: `^float` o `float$` no cuentan
    return lit is not None and forbidden.search(lit) is not None and forbidden.search(f" {lit} ") is not None


def conflicts(rules: list["BusinessRule"]) -> list[str]:
    """
    Avisos de reglas que se contradicen (nadie puede cumplir las dos) o que están duplicadas (mismo patrón y rutas,
    o mismo título o descripción con otro `id`). No invalidan el archivo: cada regla se sigue verificando.
    """
    out: list[str] = []
    forbidden = {r.id: re.compile(r.forbidden) for r in rules if r.forbidden}
    # Una regla consigo misma también puede contradecirse (prohibido y obligatorio a la vez)
    for a in rules:
        for b in rules:
            if a.id not in forbidden or not b.required or not _overlap(a.paths, b.paths):
                continue
            if not _forces_forbidden(forbidden[a.id], b.required):
                continue
            if a is b:
                out.append(f"{a.id} se contradice: `obligatorio` (`{a.required}`) siempre incluye lo `prohibido` (`{a.forbidden}`); nunca puede cumplirse")
            else:
                out.append(
                    f"{a.id} y {b.id} se contradicen: {b.id} exige `{b.required}` y {a.id} prohíbe `{a.forbidden}` en las mismas rutas; "
                    "no pueden cumplirse las dos"
                )
    for i, a in enumerate(rules):
        for b in rules[i + 1:]:
            same: list[str] = []
            if (a.forbidden or a.required) and (a.forbidden, a.required, set(a.paths)) == (b.forbidden, b.required, set(b.paths)):
                same.append("el mismo patrón y rutas")
            if _norm(a.title) == _norm(b.title):
                same.append("el mismo título")
            if _norm(a.description) == _norm(b.description):
                same.append("la misma descripción")
            if same:
                out.append(f"{b.id} parece duplicada de {a.id}: tiene {' y '.join(same)}")
    return list(dict.fromkeys(out))[:MAX_WARNINGS]


class RulesError(ValueError):
    """El archivo no es válido. El mensaje lo ve el usuario (terminal y API)."""


@dataclass(frozen=True)
class Scenario:
    """Un escenario *Dado / Cuando / Entonces* (`[[regla.escenario]]`): el puente entre el documento y la prueba."""

    given: str
    when: str
    then: str

    def text(self) -> str:
        return f"Dado {self.given}, cuando {self.when}, entonces {self.then}"


@dataclass(frozen=True)
class BusinessRule:
    id: str
    title: str
    description: str
    severity: str
    paths: tuple[str, ...] = ()
    forbidden: str | None = None
    required: str | None = None
    ai: bool = False
    story: str | None = None
    owner: str | None = None
    criterion: str | None = None
    # Formato v2
    tipo: str | None = None
    # borrador | aprobada (sin `estado`: aprobada, por compatibilidad con v1). Solo las aprobadas se verifican
    status: str = "aprobada"
    source: str | None = None
    doubts: tuple[str, ...] = ()
    # Los de `[[regla.escenario]]` o, si no hay, el `criterio` leído como escenario
    scenarios: tuple[Scenario, ...] = ()

    @property
    def approved(self) -> bool:
        return self.status == "aprobada"

    @property
    def process(self) -> bool:
        """Regla humana u organizacional: fuera del código, no se verifica ni cuenta."""
        return self.tipo == "proceso"


@dataclass(frozen=True)
class RuleSet:
    project: str
    version: str | None
    rules: list[BusinessRule]
    # 1 o 2 (`formato` en [proyecto]; 1 si falta)
    format: int = 1
    # Campos obsoletos y reglas aprobadas con dudas abiertas: no invalidan el archivo
    warnings: list[str] = field(default_factory=list)

    @property
    def approved(self) -> list[BusinessRule]:
        return [r for r in self.rules if r.approved]

    @property
    def drafts(self) -> list[BusinessRule]:
        return [r for r in self.rules if not r.approved]


@dataclass(frozen=True)
class Evidence:
    file: str
    line: int
    text: str


@dataclass(frozen=True)
class LinkedTest:
    """Prueba ligada a una o más reglas (por marcador o por nombre)."""

    name: str
    file: str
    line: int
    rules: tuple[str, ...]
    # passed | failed | broken | error | skipped | not_run (del plugin) o sin_ejecutar (encontrada leyendo el código).
    # broken = falló por otra cosa que un assert (preparar, un fixture, un import): la prueba está rota
    outcome: str = "sin_ejecutar"
    message: str = ""


@dataclass
class RuleResult:
    rule: BusinessRule
    status: Status
    level: Level
    detail: str
    evidence: list[Evidence] = field(default_factory=list)
    evidence_total: int = 0
    # Pruebas de la regla (las que fallan primero; máx. MAX_TESTS)
    tests: list[LinkedTest] = field(default_factory=list)


@dataclass
class RulesCheck:
    """Resultado del paso "Verificando reglas de negocio". `source` = None: no hay reglas declaradas."""

    source: str | None = None
    project: str | None = None
    error: str | None = None
    results: list[RuleResult] = field(default_factory=list)
    origin: Origin | None = None
    # Error del archivo del repo cuando en su lugar se usaron las reglas corregidas en la app (origin = "app")
    repo_error: str | None = None
    # Pruebas que usan reglas que no existen, etc. No detienen nada.
    warnings: list[str] = field(default_factory=list)
    # Las pruebas se ejecutaron (sandbox); False = solo se encontraron leyendo el código
    tests_ran: bool = False
    # Internos (no se guardan): resultado del patrón por regla y pruebas encontradas leyendo el código
    patterns: list[RuleResult] = field(default_factory=list, repr=False)
    declared: list[LinkedTest] = field(default_factory=list, repr=False)
    # Avisos del archivo (campos obsoletos, borradores) y reglas en borrador: no se verifican ni salen en el reporte
    notes: list[str] = field(default_factory=list, repr=False)
    drafts: tuple[str, ...] = field(default=(), repr=False)

    def count(self, status: Status) -> int:
        return sum(r.status == status for r in self.results)

    @property
    def tests_total(self) -> int:
        return len({t.name for r in self.results for t in r.tests})


# ───────────────────────── Lectura y validación ─────────────────────────


def _rule_lines(text: str) -> list[int]:
    """Línea (1-based) de cada encabezado `[[regla]]`, para ubicar los errores en el archivo."""
    return [n for n, line in enumerate(text.splitlines(), start=1) if re.match(r"\s*\[\[\s*regla\s*\]\]", line)]


def contradiction_comment(a: str, b: str, reason: str) -> str:
    """Comentario con el que el importador marca dos reglas que el documento contradice (ver `_check_marked_contradictions`)."""
    return f"# CONTRADICCIÓN {a} {b}: {reason}"


def _check_marked_contradictions(text: str, ids: set[str]) -> None:
    """
    El importador marca con `# CONTRADICCIÓN RN-004 RN-009: …` las reglas que el documento dice de dos formas
    incompatibles. Mientras existan las dos el archivo no es válido: el equipo deja la que vale (o borra el comentario si
    decide que no se contradicen). Si ya solo queda una, el comentario no estorba.
    """
    for n, line in enumerate(text.splitlines(), start=1):
        m = MARKED_CONTRADICTION.match(line)
        if not m:
            continue
        a, b, reason = m.group(1).upper(), m.group(2).upper(), m.group(3).strip()
        if a != b and a in ids and b in ids:
            detail = f": {reason}" if reason else ""
            raise RulesError(
                f"línea {n}: {a} y {b} se contradicen según el documento{detail}. Deja solo la regla que vale y borra el "
                "comentario «# CONTRADICCIÓN» (o bórralo si decides que no se contradicen)"
            )


def _text(rule: dict, key: str, where: str, limit: int, required: bool) -> str | None:
    value = rule.get(key)
    if value is None:
        if required:
            raise RulesError(f"{where}: falta `{key}`")
        return None
    if not isinstance(value, str):
        raise RulesError(f"{where}: `{key}` debe ser texto")
    value = value.strip()
    if not value:
        if required:
            raise RulesError(f"{where}: `{key}` está vacío")
        return None
    if len(value) > limit:
        raise RulesError(f"{where}: `{key}` es demasiado largo (máx. {limit} caracteres)")
    return value


def _path(raw: object, where: str) -> str:
    """Ruta relativa al repo con "/"; las carpetas conservan su "/" final."""
    if not isinstance(raw, str):
        raise RulesError(f"{where}: cada elemento de `rutas` debe ser texto")
    path = raw.strip().replace("\\", "/")
    while path.startswith(("./", "/")):
        path = path.removeprefix("./").lstrip("/")
    parts = [p for p in path.split("/") if p]
    if not parts or ".." in parts or ":" in parts[0]:
        raise RulesError(f"{where}: «{raw}» no es una ruta válida en `rutas`. Usa rutas relativas al repositorio, p. ej. app/pagos/")
    return "/".join(parts) + ("/" if path.endswith("/") else "")


def _pattern(rule: dict, key: str, where: str) -> str | None:
    pattern = _text(rule, key, where, MAX_PATTERN, required=False)
    if pattern is None:
        return None
    try:
        re.compile(pattern)
    except re.error as exc:
        raise RulesError(f"{where}: `{key}` no es una expresión regular válida ({exc})") from exc
    return pattern


def _scenarios(raw: dict, where: str) -> tuple[Scenario, ...]:
    items = raw.get("escenario", [])
    if isinstance(items, dict):
        raise RulesError(f"{where}: cada escenario va en su propia tabla [[regla.escenario]] (doble corchete)")
    if not isinstance(items, list):
        raise RulesError(f"{where}: `escenario` debe ser una lista de tablas [[regla.escenario]]")
    if len(items) > MAX_SCENARIOS:
        raise RulesError(f"{where}: máximo {MAX_SCENARIOS} escenarios por regla (tiene {len(items)})")
    out: list[Scenario] = []
    for n, item in enumerate(items, start=1):
        at = f"{where} · escenario {n}"
        if not isinstance(item, dict):
            raise RulesError(f"{at}: cada escenario va en una tabla [[regla.escenario]] con dado, cuando y entonces")
        unknown = sorted(set(item) - set(SCENARIO_FIELDS))
        if unknown:
            raise RulesError(f"{at}: campo desconocido `{unknown[0]}` (campos válidos: dado, cuando, entonces)")
        given, when, then = (_text(item, k, at, MAX_TEXT, required=True) for k in SCENARIO_FIELDS)
        out.append(Scenario(given, when, then))
    return tuple(out)


def criterion_scenario(criterion: str | None) -> Scenario | None:
    """El `criterio` v1 como escenario, si tiene la forma «Dado …, cuando …, entonces …»."""
    m = CRITERION_RE.match(criterion or "")
    return Scenario(m.group("dado"), m.group("cuando"), m.group("entonces")) if m else None


def _doubts(raw: dict, where: str) -> tuple[str, ...]:
    items = raw.get("dudas", [])
    if not isinstance(items, list) or not all(isinstance(d, str) for d in items):
        raise RulesError(f"{where}: `dudas` debe ser una lista de textos, p. ej. [\"¿Se avisa o se bloquea?\"]")
    if len(items) > MAX_DOUBTS:
        raise RulesError(f"{where}: máximo {MAX_DOUBTS} dudas por regla")
    for d in items:
        if len(d.strip()) > MAX_DOUBT:
            raise RulesError(f"{where}: cada duda admite máximo {MAX_DOUBT} caracteres")
    return tuple(dict.fromkeys(d.strip() for d in items if d.strip()))


def _choice(raw: dict, key: str, where: str, options: tuple[str, ...]) -> str | None:
    value = _text(raw, key, where, 20, required=False)
    if value is not None and value not in options:
        raise RulesError(f"{where}: `{key}` debe ser {', '.join(options[:-1])} o {options[-1]} (no «{value}»)")
    return value


def _rule(raw: object, where: str) -> BusinessRule:
    if not isinstance(raw, dict):
        raise RulesError(f"{where}: cada regla va en su propia tabla [[regla]]")
    unknown = sorted(set(raw) - RULE_FIELDS)
    if unknown:
        raise RulesError(f"{where}: campo desconocido `{unknown[0]}` (campos válidos: {', '.join(sorted(RULE_FIELDS))})")
    rule_id = _text(raw, "id", where, 16, required=True)
    if not ID_RE.match(rule_id):
        raise RulesError(f"{where}: `{rule_id}` no cumple el formato `RN-###` (p. ej. RN-001)")
    where = f"{where} · {rule_id}"
    severity = _text(raw, "severidad", where, 10, required=True)
    if severity not in SEVERITIES:
        raise RulesError(f"{where}: `severidad` debe ser alta, media o baja (no «{severity}»)")
    paths = raw.get("rutas", [])
    if not isinstance(paths, list):
        raise RulesError(f"{where}: `rutas` debe ser una lista, p. ej. [\"app/pagos/\"]")
    if len(paths) > MAX_PATHS:
        raise RulesError(f"{where}: `rutas` admite máximo {MAX_PATHS} elementos")
    ai = raw.get("ia", False)
    if not isinstance(ai, bool):
        raise RulesError(f"{where}: `ia` debe ser true o false")
    criterion = _text(raw, "criterio", where, MAX_TEXT, required=False)
    scenarios = _scenarios(raw, where)
    if not scenarios and (from_criterion := criterion_scenario(criterion)):
        scenarios = (from_criterion,)
    return BusinessRule(
        id=rule_id,
        title=_text(raw, "titulo", where, MAX_TITLE, required=True),
        description=_text(raw, "descripcion", where, MAX_TEXT, required=True),
        severity=severity,
        paths=tuple(dict.fromkeys(_path(p, where) for p in paths)),
        forbidden=_pattern(raw, "prohibido", where),
        required=_pattern(raw, "obligatorio", where),
        ai=ai,
        story=_text(raw, "historia", where, MAX_TITLE, required=False),
        owner=_text(raw, "responsable", where, MAX_TITLE, required=False),
        criterion=criterion,
        tipo=_choice(raw, "tipo", where, TYPES),
        status=_choice(raw, "estado", where, STATES) or "aprobada",
        source=_text(raw, "fuente", where, MAX_TITLE, required=False),
        doubts=_doubts(raw, where),
        scenarios=scenarios,
    )


def _rule_warnings(rule: BusinessRule, raw: dict) -> list[str]:
    """Avisos que no invalidan el archivo: campos obsoletos y reglas aprobadas con dudas abiertas."""
    out: list[str] = []
    if "obligatorio" in raw:
        out.append(
            f"{rule.id}: `obligatorio` está obsoleto (un archivo que no lo tenga, como un __init__.py vacío, ya no cumple); "
            "verifica la regla con una prueba"
        )
    if "ia" in raw:
        out.append(f"{rule.id}: `ia` ya no se usa y se ignora; la evidencia de apoyo existe para todas las reglas")
    if rule.approved and rule.doubts:
        out.append(f"{rule.id} está aprobada con {len(rule.doubts)} duda(s) abierta(s): resuélvelas o vuélvela a borrador")
    return out


def parse(text: str) -> RuleSet:
    """Reglas de un `reglas_negocio.toml`. RulesError (con la línea cuando se puede) si no es válido."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise RulesError(f"{FILENAME} no es TOML válido: {exc}") from exc
    if "reglas" in data:
        raise RulesError(f"{FILENAME}: las reglas van en tablas [[regla]] (en singular), no en [reglas]")
    unknown = sorted(set(data) - {"proyecto", "regla"})
    if unknown:
        raise RulesError(f"{FILENAME}: sección desconocida `{unknown[0]}` (se esperan [proyecto] y [[regla]])")

    project = data.get("proyecto")
    if not isinstance(project, dict):
        raise RulesError(f"{FILENAME}: falta la sección [proyecto] con su `nombre`")
    extra = sorted(set(project) - PROJECT_FIELDS)
    if extra:
        raise RulesError(f"[proyecto]: campo desconocido `{extra[0]}` (campos válidos: nombre, version, formato)")
    name = _text(project, "nombre", "[proyecto]", MAX_TITLE, required=True)
    version = project.get("version")
    if version is not None and not isinstance(version, (str, int, float)):
        raise RulesError("[proyecto]: `version` debe ser texto, p. ej. \"1.2\"")
    fmt = project.get("formato", 1)
    if fmt not in (1, 2) or isinstance(fmt, bool):
        raise RulesError("[proyecto]: `formato` debe ser 1 o 2")

    raw_rules = data.get("regla", [])
    if isinstance(raw_rules, dict):
        raise RulesError(f"{FILENAME}: cada regla va en una tabla [[regla]] (doble corchete), no en [regla]")
    if len(raw_rules) > MAX_RULES:
        raise RulesError(f"{FILENAME}: máximo {MAX_RULES} reglas (tiene {len(raw_rules)})")

    lines = _rule_lines(text)
    rules: list[BusinessRule] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for i, raw in enumerate(raw_rules):
        where = f"línea {lines[i]}" if i < len(lines) else f"regla #{i + 1}"
        rule = _rule(raw, where)
        if rule.id in seen:
            raise RulesError(f"{where}: {rule.id} está repetida")
        seen.add(rule.id)
        rules.append(rule)
        warnings += _rule_warnings(rule, raw)
    _check_marked_contradictions(text, seen)
    return RuleSet(project=name, version=None if version is None else str(version), rules=rules, format=fmt, warnings=warnings[:MAX_WARNINGS])


# ───────────────────────── Editar campos v2 en el texto ─────────────────────────

# Una clave de la tabla de la regla: `estado = "x"`, `dudas = [...]` (también en varias líneas)
_KEY_LINE = re.compile(r"^(\s*)([A-Za-z_]+)\s*=")
_TABLE_LINE = re.compile(r"^\s*\[")


def _toml_value(value: str | list[str]) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(_toml_str(v) for v in value) + "]"
    return _toml_str(value)


def set_fields(text: str, rule_id: str, updates: dict[str, str | list[str] | None]) -> str:
    """
    El texto con los campos de una regla cambiados (`None` = quitarlo), sin tocar lo demás: comentarios, orden, el
    resto de las reglas. Es lo que usa la app para aprobar, volver a borrador o resolver dudas en las reglas cargadas.
    RulesError si la regla no está o el resultado no es válido.
    """
    lines = text.splitlines()
    heads = [n - 1 for n in _rule_lines(text)]
    block = None
    for i, start in enumerate(heads):
        end = heads[i + 1] if i + 1 < len(heads) else len(lines)
        # La tabla de la regla termina en su primer [[regla.escenario]] (o en cualquier otra tabla)
        own_end = next((j for j in range(start + 1, end) if _TABLE_LINE.match(lines[j])), end)
        if any(re.match(rf'^\s*id\s*=\s*["\']{re.escape(rule_id)}["\']', lines[j]) for j in range(start + 1, own_end)):
            block = (start, own_end)
            break
    if block is None:
        raise RulesError(f"{rule_id} no está en las reglas")
    start, end = block
    keys: dict[str, tuple[int, int]] = {}
    j = start + 1
    while j < end:
        m = _KEY_LINE.match(lines[j])
        if not m:
            j += 1
            continue
        last = j
        # Un arreglo en varias líneas sigue hasta su `]`
        if "[" in lines[j].split("=", 1)[1] and "]" not in lines[j].split("=", 1)[1]:
            while last + 1 < end and "]" not in lines[last]:
                last += 1
        keys[m.group(2)] = (j, last)
        j = last + 1
    # Las líneas nuevas van después de `severidad` (o de la última clave de la regla)
    anchor = keys.get("severidad", max(keys.values(), default=(start, start)))[1]
    inserts: list[str] = []
    replaced: dict[int, tuple[int, str | None]] = {}
    for key, value in updates.items():
        line = None if value is None else f"{key.ljust(11)} = {_toml_value(value)}"
        if key in keys:
            replaced[keys[key][0]] = (keys[key][1], line)
        elif line is not None:
            inserts.append(line)
    out: list[str] = []
    skip_to = -1
    for n, line in enumerate(lines):
        if n in replaced:
            last, new = replaced[n]
            skip_to = last
            if new is not None:
                out.append(new)
        elif n > skip_to:
            out.append(line)
        # El ancla puede ser la última línea de una clave reemplazada: lo nuevo va igual después
        if n == anchor:
            out += inserts
    result = "\n".join(out) + ("\n" if text.endswith("\n") else "")
    parse(result)
    return result


def find(root: Path) -> tuple[str, str] | None:
    """(ruta relativa, contenido) del archivo de reglas del clon, o None si no hay. RulesError si no se puede leer."""
    base = root.resolve()
    for rel in LOCATIONS:
        path = root / rel
        if not path.is_file():
            continue
        # Un enlace simbólico que apunte fuera del clon no se lee
        if not path.resolve().is_relative_to(base):
            raise RulesError(f"{rel} apunta fuera del repositorio")
        if path.stat().st_size > MAX_BYTES:
            raise RulesError(f"{rel} es demasiado grande (máx. {MAX_BYTES // 1024} KB)")
        try:
            return rel, path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise RulesError(f"{rel} no está en UTF-8") from exc
    return None


# ───────────────────────── Nivel patrón ─────────────────────────


def _in_scope(file: str, paths: tuple[str, ...]) -> bool:
    return not paths or is_excluded(file, list(paths))


def scope(rule: BusinessRule, files: list[str]) -> list[str]:
    """Archivos .py del proyecto (sin pruebas) donde aplica la regla."""
    return [f for f in files if PurePosixPath(f).suffix == ".py" and not is_test_path(f) and _in_scope(f, rule.paths)]


def check_rule(rule: BusinessRule, files: list[str], read_lines: Callable[[str], list[str] | None]) -> RuleResult:
    """Nivel patrón de una regla. Sin patrón: level "ninguno" (la verifican, si las tiene, sus pruebas)."""
    if rule.forbidden is None and rule.required is None:
        return RuleResult(rule, "sin_verificar", "ninguno", "Sin patrón")
    targets = scope(rule, files)
    if not targets:
        where = ", ".join(rule.paths) if rule.paths else "el repositorio"
        return RuleResult(rule, "sin_verificar", "patron", f"No hay archivos .py (fuera de las pruebas) en {where}: revisa `rutas`.")

    evidence: list[Evidence] = []
    total = 0
    forbidden_hits = missing = with_code = 0
    forbidden = re.compile(rule.forbidden) if rule.forbidden else None
    required = re.compile(rule.required) if rule.required else None
    for file in targets:
        lines = [line.rstrip("\r") for line in (read_lines(file) or [])]
        checked = [(n, line) for n, line in enumerate(lines, start=1) if len(line) <= MAX_LINE]
        if forbidden:
            for n, line in checked:
                if forbidden.search(line):
                    forbidden_hits += 1
                    total += 1
                    if len(evidence) < MAX_EVIDENCE:
                        evidence.append(Evidence(file=file, line=n, text=line.strip()[:200]))
        # Un archivo vacío (p. ej. __init__.py) no tiene nada que deba llevar el patrón
        if not required or not any(line.strip() for line in lines):
            continue
        with_code += 1
        if not any(required.search(line) for _, line in checked):
            missing += 1
            total += 1
            if len(evidence) < MAX_EVIDENCE:
                evidence.append(Evidence(file=file, line=1, text=f"no aparece `{rule.required}`"))

    n_files = f"{len(targets)} archivo(s)"
    if forbidden_hits or missing:
        parts = []
        if forbidden_hits:
            parts.append(f"`prohibido` aparece en {forbidden_hits} línea(s)")
        if missing:
            parts.append(f"falta `obligatorio` en {missing} de {with_code} archivo(s) con código")
        return RuleResult(rule, "no_cumple", "patron", "; ".join(parts), evidence, total)
    checks = []
    if forbidden:
        checks.append("`prohibido` no aparece")
    if required:
        checks.append("`obligatorio` aparece en todos")
    return RuleResult(rule, "cumple", "patron", f"{' y '.join(checks)} ({n_files} revisado(s))")


# ───────────────────────── Nivel pruebas ─────────────────────────


def _mark_ids(node: ast.expr) -> list[str]:
    """IDs de `pytest.mark.regla("RN-001", …)` / `mark.regla(…)`; [] si la expresión es otra cosa."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "regla":
        return []
    owner = node.func.value
    if not (isinstance(owner, ast.Attribute) and owner.attr == "mark") and not (isinstance(owner, ast.Name) and owner.id == "mark"):
        return []
    ids: list[str] = []
    for arg in node.args:
        values = arg.elts if isinstance(arg, (ast.List, ast.Tuple)) else [arg]
        ids += [v.value.strip().upper() for v in values if isinstance(v, ast.Constant) and isinstance(v.value, str)]
    return ids


def _marks(nodes: list[ast.expr]) -> list[str]:
    return [i for n in nodes for i in _mark_ids(n)]


def _module_marks(tree: ast.Module) -> list[str]:
    """`pytestmark = pytest.mark.regla(…)` (o una lista de marcadores) al nivel del módulo."""
    ids: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets):
            value = node.value
            ids += _marks(list(value.elts) if isinstance(value, (ast.List, ast.Tuple)) else [value])
    return ids


def _test_rules(fn: ast.FunctionDef | ast.AsyncFunctionDef, inherited: list[str]) -> tuple[str, ...]:
    ids = inherited + _marks(fn.decorator_list)
    match = TEST_NAME_RE.match(fn.name)
    if match:
        ids.append(f"RN-{match.group(1)}")
    return tuple(sorted({i for i in ids if i}))


def linked_in_source(file: str, source: str) -> list[LinkedTest]:
    """Pruebas ligadas a reglas en un archivo de pruebas, sin ejecutarlo (mismo criterio que el plugin)."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    module = _module_marks(tree)
    found: list[LinkedTest] = []

    def add(fn: ast.FunctionDef | ast.AsyncFunctionDef, name: str, inherited: list[str]) -> None:
        if fn.name.startswith("test"):
            rules = _test_rules(fn, inherited)
            if rules:
                # Primera línea con sus decoradores: la misma que reporta pytest
                found.append(LinkedTest(name=name, file=file, line=min([fn.lineno, *(d.lineno for d in fn.decorator_list)]), rules=rules))

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add(node, f"{file}::{node.name}", module)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            inherited = module + _marks(node.decorator_list)
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    add(item, f"{file}::{node.name}::{item.name}", inherited)
    return found


def declared_tests(files: list[str], read_lines: Callable[[str], list[str] | None]) -> list[LinkedTest]:
    """Pruebas ligadas a reglas en los archivos de prueba del repo (`files` ya sin rutas excluidas)."""
    found: list[LinkedTest] = []
    for file in files:
        if PurePosixPath(file).suffix != ".py" or not is_test_path(file):
            continue
        lines = read_lines(file)
        if not lines:
            continue
        source = "\n".join(line.rstrip("\r") for line in lines)
        if len(source) > MAX_TEST_FILE or ("regla" not in source and "test_rn" not in source.lower()):
            continue
        found += linked_in_source(file, source)
    return found


def plugin_tests(data: dict | None) -> list[LinkedTest] | None:
    """Pruebas del `reglas.json` que escribe el plugin en el sandbox; None si falta o no tiene el formato."""
    if not isinstance(data, dict) or not isinstance(data.get("tests"), list):
        return None
    out: list[LinkedTest] = []
    for t in data["tests"]:
        if not isinstance(t, dict) or not isinstance(t.get("rules"), list):
            continue
        line = t.get("line")
        out.append(LinkedTest(
            name=str(t.get("nodeid") or "?")[:300],
            file=str(t.get("file") or "").replace("\\", "/")[:300],
            line=line if isinstance(line, int) and line > 0 else 1,
            rules=tuple(dict.fromkeys(str(r).strip().upper()[:32] for r in t["rules"] if str(r).strip())),
            outcome=_outcome(t),
            message=str(t.get("message") or "")[:300],
        ))
    return out


def _outcome(test: dict) -> str:
    """
    Resultado de la prueba según el plugin. Desde la versión 2 trae el tipo de la excepción: un `error` (falló al
    preparar) o una falla que no es un assert es una prueba rota. Sin `exception` (versión 1) una falla cuenta como falla.
    """
    outcome = str(test.get("outcome") or "not_run")
    exception = str(test.get("exception") or "")
    if outcome == "error" and "exception" in test:
        return "broken"
    if outcome == "failed" and exception and exception not in ASSERT_EXCEPTIONS:
        return "broken"
    return outcome


def hint_for(rule_id: str) -> str:
    return f'@pytest.mark.regla("{rule_id}") (o llamada test_{rule_id.replace("-", "").lower()}_…)'


# Si una regla tiene varias pruebas (o prueba y patrón), manda el estado más grave
PRIORITY = ("no_cumple", "prueba_rota", "no_implementada", "sin_verificar", "cumple")


@dataclass(frozen=True)
class AppNote:
    """Estado que la app ya sabe sin ejecutar (prueba generada y aprobada): no implementada o fuera del código."""

    status: Status
    detail: str


def combine(pattern: RuleResult, tests: list[LinkedTest], reason: str | None, note: AppNote | None = None) -> RuleResult:
    """
    Estado de la regla con su patrón y sus pruebas (`reason` = por qué no se ejecutaron; None = sí corrieron):
    no cumple si una prueba falla en un assert o aparece el patrón; prueba rota si falla por otra cosa (preparar, un
    fixture, un import); cumple si todo lo que la verifica pasó; si no, sin verificar. `note` = lo que la app sabe sin
    ejecutar (no implementada, fuera del código); solo se usa si la regla no tiene pruebas ni patrón.
    """
    rule = pattern.rule
    if rule.process and not tests and pattern.level == "ninguno":
        return RuleResult(rule, "fuera_del_codigo", "ninguno", 'Regla de proceso (tipo = "proceso"): no está en el código, no se verifica')
    if note is not None and not tests and pattern.level == "ninguno":
        return RuleResult(rule, note.status, "ninguno", note.detail, pattern.evidence, pattern.evidence_total)
    has_pattern = pattern.level != "ninguno"
    statuses: list[str] = [pattern.status] if has_pattern else []
    parts = [pattern.detail] if has_pattern else []
    n = len(tests)
    failing = [t for t in tests if t.outcome in ("failed", "error")]
    broken = [t for t in tests if t.outcome == "broken"]
    if tests:
        if reason:
            statuses.append("sin_verificar")
            parts.append(f"{n} prueba(s) sin ejecutar: {reason}")
        elif failing:
            statuses.append("no_cumple")
            parts.append(f"{len(failing)} de {n} prueba(s) falla(n)" + (f"; {len(broken)} rota(s)" if broken else ""))
        elif broken:
            statuses.append("prueba_rota")
            parts.append(f"{len(broken)} de {n} prueba(s) rota(s): fallan al preparar el escenario, no por el código. Revisa la prueba")
        elif passed := sum(t.outcome == "passed" for t in tests):
            statuses.append("cumple")
            parts.append(f"{passed} prueba(s) pasan" + (f" ({n - passed} omitida(s))" if passed < n else ""))
        else:
            statuses.append("sin_verificar")
            parts.append(f"sus {n} prueba(s) se omitieron o no corrieron")
    if not statuses:
        status: Status = "sin_verificar"
        detail = f"Sin patrón ni pruebas: agrega `prohibido` u `obligatorio`, o una prueba con {hint_for(rule.id)}."
    else:
        status = next(s for s in PRIORITY if s in statuses)
        detail = "; ".join(parts)
    level: Level = ("pruebas_y_patron" if tests else "patron") if has_pattern else ("pruebas" if tests else "ninguno")
    ordered = failing + broken + [t for t in tests if t not in failing and t not in broken]
    return RuleResult(rule, status, level, detail, pattern.evidence, pattern.evidence_total, ordered[:MAX_TESTS])


def _warnings(source: str, rule_ids: set[str], tests: list[LinkedTest], drafts: tuple[str, ...] = ()) -> list[str]:
    out: list[str] = []
    for t in tests:
        for rid in t.rules:
            if not ID_RE.match(rid):
                out.append(f"{t.name} usa «{rid}», que no cumple el formato RN-###")
            elif rid not in rule_ids and rid not in drafts:
                out.append(f"{t.name} usa {rid}, que no está en {source}")
    return list(dict.fromkeys(out))[:MAX_WARNINGS]


def _with(check: RulesCheck, tests: list[LinkedTest], reason: str | None, notes: dict[str, AppNote] | None = None) -> RulesCheck:
    notes = notes or {}
    results = [combine(p, [t for t in tests if p.rule.id in t.rules], reason, notes.get(p.rule.id)) for p in check.patterns]
    ids = {p.rule.id for p in check.patterns}
    warnings = check.notes + conflicts([p.rule for p in check.patterns]) + _warnings(check.source or FILENAME, ids, tests, check.drafts)
    return replace(check, results=results, warnings=list(dict.fromkeys(warnings))[:MAX_WARNINGS], tests_ran=reason is None)


def drafts_note(drafts: list[BusinessRule]) -> str | None:
    if not drafts:
        return None
    ids = ", ".join(r.id for r in drafts[:8]) + ("…" if len(drafts) > 8 else "")
    return f"{len(drafts)} regla(s) en borrador no se verifican ni salen en el reporte ({ids}): apruébalas en Configuración → Reglas de negocio"


# Sin sandbox (o sin que pytest corra) las pruebas ligadas se encuentran leyendo el código
PENDING = "se ejecutan en el sandbox"


def merge_app_tests(repo: dict | None, app: dict | None) -> dict | None:
    """
    reglas.json de las pruebas del repo + el de las pruebas generadas por IA voy y aprobadas en la app (otra corrida
    de pytest sobre tests/_ia_voy_reglas/). Las del repo tienen prioridad: de la app solo cuentan las de reglas que el
    repo no prueba.
    """
    app_tests = app.get("tests") if isinstance(app, dict) else None
    if not isinstance(app_tests, list) or not app_tests:
        return repo
    repo_tests = plugin_tests(repo)
    covered = {r for t in repo_tests or [] for r in t.rules}
    extra = [
        t for t in app_tests
        if isinstance(t, dict) and isinstance(t.get("rules"), list) and not covered & {str(r).strip().upper() for r in t["rules"]}
    ]
    base = repo if repo_tests is not None else {"version": 2, "tests": []}
    return {**base, "tests": [*base["tests"], *extra]}


def with_app(check: RulesCheck, declared: list[LinkedTest], notes: dict[str, AppNote]) -> RulesCheck:
    """
    Suma lo aprobado en la app (app.projects.reglas_pruebas.analysis_inputs): sus pruebas como «declaradas» (para cuando
    no corren) en las reglas que el repo no prueba, y los estados que se saben sin ejecutar.
    """
    if check.error or not check.patterns or not (declared or notes):
        return check
    covered = {r for t in check.declared for r in t.rules}
    check = replace(check, declared=check.declared + [t for t in declared if not covered & set(t.rules)])
    return _with(check, check.declared, PENDING, notes)


def with_tests(check: RulesCheck | None, data: dict | None, reason: str | None, notes: dict[str, AppNote] | None = None) -> RulesCheck | None:
    """
    Agrega el resultado de las pruebas: las del plugin (`data`, de reglas.json) si corrieron en el sandbox
    (`reason` = None), o las encontradas leyendo el código con `reason` = por qué no se ejecutaron. `notes` = lo que la
    app ya sabe de reglas sin prueba (no implementada, fuera del código).
    """
    if check is None or check.error or not check.patterns:
        return check
    if reason is None:
        ran = plugin_tests(data)
        if ran is not None:
            return _with(check, ran, None, notes)
        reason = "pytest no pudo correr las pruebas"
    return _with(check, check.declared, reason, notes)


def run(
    root: Path, files: list[str], read_lines: Callable[[str], list[str] | None], uploaded: str | None = None,
) -> RulesCheck:
    """
    Paso "Verificando reglas de negocio" sobre el clon. `files` = archivos del repo ya sin las rutas excluidas;
    `uploaded` = reglas cargadas en la app: se usan si el repo no tiene el archivo o si el suyo no es válido
    (entonces `repo_error` dice por qué). Un archivo válido del repo siempre gana.
    Las pruebas quedan "sin ejecutar" hasta `with_tests`.
    Nunca lanza por culpa del archivo: un archivo inválido queda en `error` y el análisis sigue.
    """
    source, ruleset, repo_error = _repo_rules(root)
    origin: Origin = "repo"
    if ruleset is None:
        app_rules: RuleSet | None = None
        if uploaded and uploaded.strip():
            try:
                app_rules = parse(uploaded)
            except RulesError as exc:
                # Se validan al guardarse; si aun así fallan, manda el error del repo (si hay)
                if repo_error is None:
                    return RulesCheck(source=APP_SOURCE, error=str(exc), origin="app")
        if app_rules is None:
            return RulesCheck(source=source, error=repo_error, origin="repo") if repo_error else RulesCheck()
        ruleset, origin = app_rules, "app"
        repo_error = f"{source}: {repo_error}" if repo_error else None
        source = APP_SOURCE
    cache: dict[str, list[str] | None] = {}

    def cached(file: str) -> list[str] | None:
        if file not in cache:
            cache[file] = read_lines(file)
        return cache[file]

    # Solo las aprobadas cuentan (PROPUESTA_REGLAS_VERIFICABLES.md §9): los borradores se ven en Configuración
    patterns = [check_rule(r, files, cached) for r in ruleset.approved]
    notes = [*ruleset.warnings, *filter(None, [drafts_note(ruleset.drafts)])]
    check = RulesCheck(
        source=source, project=ruleset.project, origin=origin, repo_error=repo_error, patterns=patterns, declared=declared_tests(files, cached),
        notes=notes, drafts=tuple(r.id for r in ruleset.drafts),
    )
    return _with(check, check.declared, PENDING)


def _repo_rules(root: Path) -> tuple[str, RuleSet | None, str | None]:
    """(archivo, reglas, error) del repo: (FILENAME, None, None) si no tiene el archivo."""
    source = FILENAME
    try:
        found = find(root)
        if found is None:
            return source, None, None
        source, text = found
        return source, parse(text), None
    except RulesError as exc:
        return source, None, str(exc)


def summary_line(check: RulesCheck | None) -> str:
    """Línea de la terminal al terminar el paso."""
    if check is None or check.source is None:
        return f"  sin reglas declaradas ({FILENAME} no está en el repositorio)"
    if check.error:
        return f"  ERROR en {check.source}: {check.error}\n  el análisis sigue sin verificar las reglas de negocio"
    if not check.results:
        return f"  {check.source} no declara reglas"
    line = (
        f"  {len(check.results)} regla(s) · {check.count('cumple')} cumplen · "
        f"{check.count('no_cumple')} no cumplen · {check.count('sin_verificar')} sin verificar"
    )
    labels = (("prueba_rota", "con la prueba rota"), ("no_implementada", "no implementada(s)"), ("fuera_del_codigo", "fuera del código"))
    extra = [f"{check.count(s)} {label}" for s, label in labels if check.count(s)]
    if extra:
        line += " · " + " · ".join(extra)
    if check.tests_total:
        line += f" · {check.tests_total} prueba(s) ligada(s)" + ("" if check.tests_ran else " sin ejecutar")
    if check.repo_error:
        line += f"\n  aviso: {check.repo_error}\n  se usaron las reglas corregidas en la app; sube el archivo corregido al repositorio"
    elif check.origin == "app":
        line += "\n  aviso: reglas cargadas en la app; súbelas al repositorio como reglas_negocio.toml"
    return "\n".join([line, *(f"  aviso: {w}" for w in check.warnings)])
