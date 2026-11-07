"""
Reglas de negocio del proyecto analizado (docs/adr/ADR-003-reglas-de-negocio.md y
docs/PROPUESTA_REGLAS_NEGOCIO.md).

Cada proyecto declara sus reglas en `reglas_negocio.toml` (raíz del repo o `docs/`) y las liga a algo
verificable. Este módulo lee y valida el archivo y verifica el nivel **patrón**: `prohibido` (regex que no debe
aparecer) y `obligatorio` (regex que debe aparecer en cada archivo) sobre los `.py` de `rutas`. Como Bandit y
Ruff, solo lee el código: no lo ejecuta. Las pruebas del proyecto no se revisan aquí: `prohibido` en una
prueba es normal (la prueba lo usa para comprobar la regla).

El nivel **pruebas** (`@pytest.mark.regla("RN-002")`, en el sandbox) llega en el Sprint 8: mientras tanto una
regla sin patrón queda "sin verificar". Los resultados se guardan aparte de los hallazgos
(app.analyses.reglas_store) y todavía no entran al score.
"""

import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
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

ID_RE = re.compile(r"^RN-\d{3}$")
SEVERITIES = ("alta", "media", "baja")
REQUIRED = ("id", "titulo", "descripcion", "severidad")
OPTIONAL_TEXT = ("historia", "responsable", "criterio")
RULE_FIELDS = {*REQUIRED, *OPTIONAL_TEXT, "rutas", "prohibido", "obligatorio", "ia"}
PROJECT_FIELDS = {"nombre", "version"}

Status = Literal["cumple", "no_cumple", "sin_verificar"]
Level = Literal["patron", "ninguno"]


class RulesError(ValueError):
    """El archivo no es válido. El mensaje lo ve el usuario (terminal y API)."""


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


@dataclass(frozen=True)
class RuleSet:
    project: str
    version: str | None
    rules: list[BusinessRule]


@dataclass(frozen=True)
class Evidence:
    file: str
    line: int
    text: str


@dataclass
class RuleResult:
    rule: BusinessRule
    status: Status
    level: Level
    detail: str
    evidence: list[Evidence] = field(default_factory=list)
    evidence_total: int = 0


@dataclass
class RulesCheck:
    """Resultado del paso "Verificando reglas de negocio". `source` = None: el repo no declara reglas."""

    source: str | None = None
    project: str | None = None
    error: str | None = None
    results: list[RuleResult] = field(default_factory=list)

    def count(self, status: Status) -> int:
        return sum(r.status == status for r in self.results)


# ───────────────────────── Lectura y validación ─────────────────────────


def _rule_lines(text: str) -> list[int]:
    """Línea (1-based) de cada encabezado `[[regla]]`, para ubicar los errores en el archivo."""
    return [n for n, line in enumerate(text.splitlines(), start=1) if re.match(r"\s*\[\[\s*regla\s*\]\]", line)]


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
        criterion=_text(raw, "criterio", where, MAX_TEXT, required=False),
    )


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
        raise RulesError(f"[proyecto]: campo desconocido `{extra[0]}` (campos válidos: nombre, version)")
    name = _text(project, "nombre", "[proyecto]", MAX_TITLE, required=True)
    version = project.get("version")
    if version is not None and not isinstance(version, (str, int, float)):
        raise RulesError("[proyecto]: `version` debe ser texto, p. ej. \"1.2\"")

    raw_rules = data.get("regla", [])
    if isinstance(raw_rules, dict):
        raise RulesError(f"{FILENAME}: cada regla va en una tabla [[regla]] (doble corchete), no en [regla]")
    if len(raw_rules) > MAX_RULES:
        raise RulesError(f"{FILENAME}: máximo {MAX_RULES} reglas (tiene {len(raw_rules)})")

    lines = _rule_lines(text)
    rules: list[BusinessRule] = []
    seen: set[str] = set()
    for i, raw in enumerate(raw_rules):
        where = f"línea {lines[i]}" if i < len(lines) else f"regla #{i + 1}"
        rule = _rule(raw, where)
        if rule.id in seen:
            raise RulesError(f"{where}: {rule.id} está repetida")
        seen.add(rule.id)
        rules.append(rule)
    return RuleSet(project=name, version=None if version is None else str(version), rules=rules)


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
    if rule.forbidden is None and rule.required is None:
        return RuleResult(
            rule, "sin_verificar", "ninguno",
            "Sin patrón: agrega `prohibido` u `obligatorio`. Las pruebas con @pytest.mark.regla se verifican desde el Sprint 8.",
        )
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


def run(root: Path, files: list[str], read_lines: Callable[[str], list[str] | None]) -> RulesCheck:
    """
    Paso "Verificando reglas de negocio" sobre el clon. `files` = archivos del repo ya sin las rutas excluidas.
    Nunca lanza por culpa del archivo: un archivo inválido queda en `error` y el análisis sigue.
    """
    try:
        found = find(root)
    except RulesError as exc:
        return RulesCheck(source=FILENAME, error=str(exc))
    if found is None:
        return RulesCheck()
    source, text = found
    try:
        ruleset = parse(text)
    except RulesError as exc:
        return RulesCheck(source=source, error=str(exc))
    cache: dict[str, list[str] | None] = {}

    def cached(file: str) -> list[str] | None:
        if file not in cache:
            cache[file] = read_lines(file)
        return cache[file]

    return RulesCheck(source=source, project=ruleset.project, results=[check_rule(r, files, cached) for r in ruleset.rules])


def summary_line(check: RulesCheck | None) -> str:
    """Línea de la terminal al terminar el paso."""
    if check is None or check.source is None:
        return f"  sin reglas declaradas ({FILENAME} no está en el repositorio)"
    if check.error:
        return f"  ERROR en {check.source}: {check.error}\n  el análisis sigue sin verificar las reglas de negocio"
    if not check.results:
        return f"  {check.source} no declara reglas"
    return (
        f"  {len(check.results)} regla(s) · {check.count('cumple')} cumplen · "
        f"{check.count('no_cumple')} no cumplen · {check.count('sin_verificar')} sin verificar"
    )
