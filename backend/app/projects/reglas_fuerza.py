"""
Prueba de fuerza de las pruebas de reglas (docs/PROPUESTA_REGLAS_VERIFICABLES.md §12.2 y §15, fase 5): mutación
**dirigida**, no completa (sería lenta).

Una prueba que pasa no basta: puede pasar aunque el código no haga lo que dice la regla (p. ej. si solo revisa que el
servidor no responda 500). Aquí se cambian a propósito las líneas que implementan la regla y se comprueba que la
prueba lo nota:
- **Qué líneas:** las que señala la evidencia de apoyo (app.projects.reglas_evidencia), si la hay; si no, las de las
  funciones de los endpoints que llama la prueba y las del proyecto que esas funciones llaman, quedándose con las que
  se parecen a la regla (palabras en común con la línea y con lo que hace su `if`).
  Si las líneas de la evidencia no tienen nada que cambiar, se amplía a la función que las contiene (con el mismo
  filtro de palabras).
- **Qué cambios (con `ast`, sin IA):** comparaciones (`<` ↔ `<=`, `==` ↔ `!=`, `in` ↔ `not in`…), condiciones
  invertidas (`if x` → `if not (x)`), `raise` quitados, `and` ↔ `or`, cuentas con constantes (`precio * PORCENTAJE` →
  `precio / PORCENTAJE`), llamadas quitadas (`correo.enviar(...)`), decoradores de permiso quitados
  (`@requiere("admin")`) y números (`n` → `n + 1`).
- **Cómo:** en el sandbox (modo `fuerza`, app.analysis.ia_voy_fuerza): la prueba con el código original y luego con
  cada mutante. Si falla, el mutante muere; si sigue pasando, la prueba no lo notó.

Resultado: **fuerte** (mató a todos), **parcial** (mató a algunos: se listan los que sobrevivieron) o **débil** (no mató
a ninguno: la prueba no verifica la regla). No cambia el estado de la regla: es un aviso para el equipo antes de aprobar.
"""

import ast
import hashlib
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.analyses import mapa, reglas
from app.projects import reglas_evidencia as evidencia
from app.projects import reglas_pruebas as pruebas

SPEC = ".ia_voy_mutantes.json"
MAX_MUTANTS = 10
MAX_TOTAL = 40
MAX_TARGETS = 8
MAX_FILE_BYTES = 300_000
# Una evidencia de hasta 4 líneas es precisa: se mutan todas sus líneas sin filtrar
PRECISE_LINES = 4
# Cambios mínimos para llamar «débil» a una prueba que no notó ninguno
MIN_WEAK = 2

SWAP: dict[type, type] = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
    ast.In: ast.NotIn, ast.NotIn: ast.In, ast.Is: ast.IsNot, ast.IsNot: ast.Is,
}
# Orden en que se eligen (los de límite primero: es donde suelen fallar las reglas)
KINDS = ("comparacion", "excepcion", "condicion", "logico", "aritmetica", "llamada", "decorador", "constante")
ARITH: dict[type, type] = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}
# Decoradores que no se quitan: registran la ruta o son de Python (quitarlos rompe todo y no dice nada de la regla)
KEEP_DECORATORS = {
    "get", "post", "put", "patch", "delete", "head", "options", "route", "api_route", "websocket", "api_view", "action",
    "fixture", "property", "staticmethod", "classmethod", "cached_property", "wraps", "cache", "lru_cache", "dataclass",
    "errorhandler", "before_request", "after_request", "teardown_request", "on_event", "middleware", "exception_handler",
    "validator", "field_validator", "model_validator", "root_validator", "receiver", "register",
}
# Llamadas que no se quitan: quitarlas no cambia lo que hace el código (registros)
KEEP_CALLS = {"log", "logger", "logging", "print", "warnings", "warn"}


@dataclass
class Target:
    file: str
    start: int
    end: int
    # evidencia | evidencia+funcion | endpoint | llamada
    source: str


@dataclass
class Mutant:
    id: str
    file: str
    line: int
    kind: str
    description: str
    code: str = field(repr=False)


# ───────────────────────── Qué líneas ─────────────────────────


def _parse(root: Path, rel: str) -> tuple[str, ast.Module] | None:
    try:
        path = root / rel
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        source = path.read_text(encoding="utf-8")
        return source, ast.parse(source)
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError):
        return None


def _functions(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _called(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Nombres que la función llama en su cuerpo (no en sus decoradores)."""
    names: set[str] = set()
    for n in (sub for stmt in fn.body for sub in ast.walk(stmt)):
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name):
                names.add(n.func.id)
            elif isinstance(n.func, ast.Attribute):
                names.add(n.func.attr)
    return names


def targets(root: Path, project_map: mapa.ProjectMap, endpoints: list[str], ev: evidencia.Evidence | None = None) -> list[Target]:
    """Las líneas que se van a mutar: las de la evidencia o, sin ella, las funciones de los endpoints y lo que llaman."""
    if ev and ev.places:
        return [Target(p.file, p.start, p.end, "evidencia") for p in ev.places]
    out: list[Target] = []
    trees: dict[str, tuple[str, ast.Module] | None] = {}

    def tree(rel: str):
        if rel not in trees:
            trees[rel] = _parse(root, rel)
        return trees[rel]

    called: list[tuple[str, set[str]]] = []
    for raw in endpoints:
        m = pruebas.ENDPOINT.match(str(raw))
        if not m:
            continue
        method, path = m.group(1).upper(), m.group(2).split("?")[0]
        concrete = re.sub(r"\{[^}]*\}|<[^>]*>", "1", path)
        for e in project_map.endpoints:
            if e.method != method or not (e.path == path or pruebas._route_pattern(e.path).match(concrete)):
                continue
            parsed = tree(e.file)
            if parsed is None:
                continue
            name = e.function.split(":")[-1]
            fns = [f for f in _functions(parsed[1]) if f.name == name]
            if not fns:
                continue
            fn = min(fns, key=lambda f: abs(f.lineno - e.line))
            t = Target(e.file, fn.lineno, fn.end_lineno or fn.lineno, "endpoint")
            if t not in out:
                out.append(t)
                called.append((e.file, _called(fn)))
    # Un nivel de llamadas: la lógica de negocio suele estar en otro módulo (citas.reservar, servicios.cobrar…)
    wanted = {n for _, names in called for n in names if not n.startswith("__")}
    if wanted:
        same_file = {f for f, _ in called}
        found: list[Target] = []
        for rel in pruebas.project_files(root):
            parsed = tree(rel)
            if parsed is None:
                continue
            for fn in _functions(parsed[1]):
                t = Target(rel, fn.lineno, fn.end_lineno or fn.lineno, "llamada")
                if fn.name in wanted and not any((o.file, o.start) == (t.file, t.start) for o in [*out, *found]):
                    found.append(t)
        # Primero las de otros módulos (dominio) y después las auxiliares del mismo archivo del endpoint
        found.sort(key=lambda t: (t.file in same_file, t.file, t.start))
        out += found
    return out[:MAX_TARGETS]


# ───────────────────────── Qué cambios ─────────────────────────


def _byte_lines(source: str) -> list[bytes]:
    return [line.encode("utf-8") for line in source.splitlines(keepends=True)]


def _segment(lines: list[bytes], node: ast.AST) -> str:
    l0, l1 = node.lineno - 1, node.end_lineno - 1
    if l0 == l1:
        return lines[l0][node.col_offset : node.end_col_offset].decode("utf-8", "replace")
    parts = [lines[l0][node.col_offset :], *lines[l0 + 1 : l1], lines[l1][: node.end_col_offset]]
    return b"".join(parts).decode("utf-8", "replace")


def _splice(lines: list[bytes], node: ast.AST, new: str) -> str:
    l0, l1 = node.lineno - 1, node.end_lineno - 1
    head = lines[l0][: node.col_offset]
    tail = lines[l1][node.end_col_offset :]
    return b"".join([*lines[:l0], head + new.encode("utf-8") + tail, *lines[l1 + 1 :]]).decode("utf-8")


def _drop_line(lines: list[bytes], node: ast.AST) -> str:
    """Quita la línea del nodo (un decorador) y deja una vacía, para no mover las demás."""
    return b"".join([*lines[: node.lineno - 1], b"\n", *lines[node.lineno :]]).decode("utf-8")


def _enclosing(root: Path, places: list[Target]) -> list[Target]:
    """Las funciones que contienen las líneas de la evidencia, o que tienen ahí un decorador (la más interna)."""
    out: list[Target] = []
    for t in places:
        parsed = _parse(root, t.file)
        if parsed is None:
            continue
        fns = _functions(parsed[1])

        def span(f):
            return min([f.lineno, *(d.lineno for d in f.decorator_list)]), f.end_lineno or f.lineno

        inside = [f for f in fns if span(f)[0] <= t.start and span(f)[1] >= t.end]
        touching = [f for f in fns if any(t.start <= d.lineno <= t.end for d in f.decorator_list)]
        for fn in [*sorted(inside, key=lambda f: f.lineno, reverse=True)[:1], *touching]:
            start, end = span(fn)
            e = Target(t.file, start, end, "evidencia+funcion")
            if e not in out:
                out.append(e)
    return out


def _short(text: str, n: int = 70) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


@dataclass
class _Candidate:
    node: ast.AST
    kind: str
    new: str
    description: str
    context: str


def _parents(tree: ast.Module) -> dict[ast.AST, ast.AST]:
    return {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}


def _context(node: ast.AST, parents: dict, lines: list[bytes], own_line: bool = False) -> str:
    """Texto para saber si la línea tiene que ver con la regla: su sentencia y, si es un `if`, lo primero que hace."""
    stmt = node
    while stmt in parents and not isinstance(stmt, ast.stmt):
        stmt = parents[stmt]
    text = lines[stmt.lineno - 1].decode("utf-8", "replace") if isinstance(stmt, ast.stmt) else ""
    # Para una cuenta en una sentencia de varias líneas, también su línea (`anticipo=dinero(precio * PORCENTAJE)`); en
    # las comparaciones no: las consultas largas comparten palabras con casi cualquier regla
    if own_line and isinstance(stmt, ast.stmt) and node.lineno != stmt.lineno:
        text += " " + lines[node.lineno - 1].decode("utf-8", "replace")
    if isinstance(stmt, (ast.If, ast.While)) and stmt.body:
        first = stmt.body[0]
        text += " " + b"".join(lines[first.lineno - 1 : (first.end_lineno or first.lineno)]).decode("utf-8", "replace")
    return text


def _in_fstring(node: ast.AST, parents: dict) -> bool:
    while node in parents:
        node = parents[node]
        if isinstance(node, ast.JoinedStr):
            return True
    return False


def _callee(node: ast.AST) -> str:
    """`@app.post("/x")` → "app.post"; `correo.enviar(...)` → "correo.enviar"."""
    func = node.func if isinstance(node, ast.Call) else node
    return mapa._name(func) or ""


def _constant_like(node: ast.AST) -> bool:
    """Un número o una constante del proyecto (`PORCENTAJE_ANTICIPO`, `cfg.LIMITE`): la cuenta es de negocio."""
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    name = node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else ""
    return len(name) > 1 and name.isupper()


def candidates(source: str, tree: ast.Module, start: int, end: int) -> list[_Candidate]:
    lines = _byte_lines(source)
    parents = _parents(tree)
    out: list[_Candidate] = []
    # Decoradores de permiso (no los de rutas): se quita la línea entera
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for d in fn.decorator_list:
            name = _callee(d)
            if not start <= d.lineno <= end or name.split(".")[-1] in KEEP_DECORATORS or d.end_lineno != d.lineno:
                continue
            line = lines[d.lineno - 1].decode("utf-8", "replace")
            if not line.lstrip().startswith("@"):
                continue
            out.append(_Candidate(d, "decorador", "", f"se quita `@{_short(_segment(lines, d))}`", line + " " + fn.name.replace("_", " ")))
    for node in ast.walk(tree):
        lineno = getattr(node, "lineno", None)
        if lineno is None or not start <= lineno <= end or _in_fstring(node, parents):
            continue
        single = node.end_lineno == lineno
        old = _segment(lines, node) if single or isinstance(node, ast.Raise) else ""
        if isinstance(node, ast.Compare) and single and len(node.ops) == 1 and type(node.ops[0]) in SWAP:
            new_node = ast.Compare(node.left, [SWAP[type(node.ops[0])]()], node.comparators)
            new = ast.unparse(new_node)
            out.append(_Candidate(node, "comparacion", new, f"`{_short(old)}` → `{_short(new)}`", _context(node, parents, lines)))
        elif isinstance(node, ast.Raise):
            out.append(_Candidate(node, "excepcion", "pass", f"se quita `{_short(old)}`", _context(node, parents, lines)))
        elif isinstance(node, ast.IfExp) and node.test.end_lineno == node.test.lineno:
            # `a if c else b` → `a if not (c) else b` (p. ej. el límite de los clientes premium)
            test = _segment(lines, node.test)
            out.append(_Candidate(node.test, "condicion", f"not ({test})", f"se invierte la condición `{_short(test)}`", _context(node, parents, lines)))
        elif isinstance(node, (ast.If, ast.While)) and node.test.end_lineno == node.test.lineno:
            test = _segment(lines, node.test)
            out.append(_Candidate(node.test, "condicion", f"not ({test})", f"se invierte la condición `{_short(test)}`", _context(node, parents, lines)))
        elif (
            isinstance(node, ast.BinOp) and single and type(node.op) in ARITH
            and (_constant_like(node.left) or _constant_like(node.right))
        ):
            new = ast.unparse(ast.BinOp(node.left, ARITH[type(node.op)](), node.right))
            out.append(_Candidate(node, "aritmetica", new, f"`{_short(old)}` → `{_short(new)}`", _context(node, parents, lines, own_line=True)))
        elif (
            isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and _callee(node.value).split(".")[0] not in KEEP_CALLS
        ):
            call = _segment(lines, node) if single else _callee(node.value) + "(…)"
            text = b"".join(lines[node.lineno - 1 : node.end_lineno]).decode("utf-8", "replace")
            out.append(_Candidate(node, "llamada", "pass", f"se quita la llamada `{_short(call)}`", text))
        elif isinstance(node, ast.BoolOp) and single:
            op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
            new = ast.unparse(ast.BoolOp(op, node.values))
            out.append(_Candidate(node, "logico", new, f"`{_short(old)}` → `{_short(new)}`", _context(node, parents, lines)))
        elif (
            isinstance(node, ast.Constant) and type(node.value) is int and single and abs(node.value) < 10**9
            # Los números de una comparación, una cuenta o un argumento con nombre (`hours=2`); no los códigos de
            # respuesta (`Error(409, …)`), que no son la regla
            and isinstance(parents.get(node), (ast.Compare, ast.BinOp, ast.keyword))
        ):
            out.append(_Candidate(node, "constante", str(node.value + 1), f"`{node.value}` → `{node.value + 1}`", _context(node, parents, lines)))
    return out


def mutants(
    root: Path, project_map: mapa.ProjectMap, rule: reglas.BusinessRule, endpoints: list[str], ev: evidencia.Evidence | None = None,
    limit: int = MAX_MUTANTS,
) -> tuple[list[Mutant], list[Target]]:
    """
    Los mutantes de la regla, deterministas. Con evidencia se mutan sus líneas; sin ella, solo las líneas de las
    funciones que se parecen a la regla (si ninguna se parece, no hay mutantes: la prueba de fuerza no aplica).
    """
    found = targets(root, project_map, endpoints, ev)
    words = pruebas._words(pruebas.rule_words(rule))

    def score(ts: list[Target]) -> list[tuple]:
        """(−relevancia, tipo, archivo, línea, candidato, código, líneas, ¿hay que filtrarlo por palabras?)"""
        out_ = []
        for t in ts:
            parsed = _parse(root, t.file)
            if parsed is None:
                continue
            source, tree = parsed
            lines = _byte_lines(source)
            # Una línea precisa de la evidencia se muta siempre; un tramo largo (una función entera) trae líneas de
            # otras reglas, y se filtra por palabras como sin evidencia
            loose = t.source != "evidencia" or t.end - t.start + 1 > PRECISE_LINES
            for c in candidates(source, tree, t.start, t.end):
                relevance = len(words & pruebas._words(c.context))
                out_.append((-relevance, KINDS.index(c.kind), t.file, c.node.lineno, c, source, lines, loose))
        return out_

    scored = score(found)
    # Las líneas de la evidencia no tienen nada que cambiar (una asignación, una llamada en varias líneas): se amplía a
    # la función que las contiene, con el mismo filtro de palabras que sin evidencia
    if found and found[0].source == "evidencia" and not scored:
        found = _enclosing(root, found)
        scored = score(found)
    # Lo que se filtra: solo las líneas que comparten al menos ¾ de las palabras de la más parecida, y al menos 2 (una
    # palabra suelta, como «cita» o «base», suele ser casualidad). Sin evidencia, 1 basta si ninguna llega a 2
    loose = [s for s in scored if s[7]]
    if loose:
        best = max(-s[0] for s in loose)
        minimum = 2 if found[0].source.startswith("evidencia") else min(2, best)
        floor = max(minimum, math.ceil(0.75 * best), 1)
        scored = [s for s in scored if not s[7] or -s[0] >= floor]
    scored.sort(key=lambda s: s[:4])
    out: list[Mutant] = []
    seen: set[str] = set()
    for _, _, file, line, c, source, lines, _ in scored:
        code = _drop_line(lines, c.node) if c.kind == "decorador" else _splice(lines, c.node, c.new)
        digest = hashlib.sha256(f"{file}\n{code}".encode()).hexdigest()
        if code == source or digest in seen:
            continue
        try:
            ast.parse(code)
        except SyntaxError:
            continue
        seen.add(digest)
        out.append(Mutant(f"{rule.id}-{len(out) + 1}", file, line, c.kind, c.description, code))
        if len(out) >= limit:
            break
    return out, found


def spec(objectives: list[tuple[str, str, list[Mutant]]]) -> dict:
    """El JSON que lee app.analysis.ia_voy_fuerza: (regla, archivo de la prueba, mutantes)."""
    return {
        "objetivos": [
            {"regla": rid, "prueba": test_file, "mutantes": [{"id": m.id, "archivo": m.file, "codigo": m.code} for m in ms]}
            for rid, test_file, ms in objectives
        ]
    }


# ───────────────────────── Resultado ─────────────────────────


@dataclass
class Survivor:
    file: str
    line: int
    description: str


@dataclass
class StrengthResult:
    # fuerte | parcial | debil | no_aplica
    status: str
    detail: str
    killed: int = 0
    total: int = 0
    survivors: list[Survivor] = field(default_factory=list)
    # Qué se mutó: evidencia o endpoints
    source: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def read(
    data: dict | None, phases: dict[str, tuple[int | None, str]], plan: dict[str, tuple[list[Mutant], list[Target]]],
) -> dict[str, StrengthResult]:
    """Resultado por regla del fuerza.json del sandbox. `plan` = regla → (mutantes, líneas que se mutaron)."""
    from app.projects import reglas_arnes as arnes

    venv, install, tests = (phases.get(p, (None, "")) for p in ("venv", "install", "tests"))
    problem = None
    if venv[0] != 0:
        problem = f"No se pudo preparar el entorno del sandbox: {arnes._tail(venv[1])}"
    elif install[0] not in (0, None):
        problem = f"No se pudieron instalar las dependencias del proyecto: {arnes._tail(install[1])}"
    elif data is None:
        problem = f"La prueba de fuerza no terminó: {arnes._tail(tests[1]) or 'se agotó el tiempo del sandbox'}"
    by_rule = {str(o.get("regla")): o for o in (data or {}).get("objetivos") or [] if isinstance(o, dict)}
    out: dict[str, StrengthResult] = {}
    for rid, (ms, found) in plan.items():
        source = found[0].source if found else ""
        if problem:
            out[rid] = StrengthResult("no_aplica", problem, source=source)
            continue
        if not ms:
            why = "No hay líneas que se parezcan a la regla en lo que llama la prueba: pide la evidencia de apoyo para elegir qué mutar"
            out[rid] = StrengthResult("no_aplica", why, source=source)
            continue
        o = by_rule.get(rid)
        if o is None:
            out[rid] = StrengthResult("no_aplica", "El sandbox no devolvió el resultado de esta regla", source=source)
            continue
        if o.get("base") != 0:
            out[rid] = StrengthResult("no_aplica", "La prueba no pasa con el código actual: la prueba de fuerza solo aplica a pruebas que pasan", source=source)
            continue
        codes = {str(r.get("id")): r.get("codigo_salida") for r in o.get("mutantes") or [] if isinstance(r, dict)}
        ran = [m for m in ms if codes.get(m.id) is not None]
        survivors = [Survivor(m.file, m.line, m.description) for m in ran if codes[m.id] == 0]
        killed = len(ran) - len(survivors)
        if not ran:
            out[rid] = StrengthResult("no_aplica", "No se pudo correr ningún mutante", source=source)
            continue
        # «Débil» pide al menos MIN_WEAK cambios: con uno solo que no notó (un límite, `gt=0` → `gt=1`) es poca base
        status = "fuerte" if not survivors else "debil" if killed == 0 and len(ran) >= MIN_WEAK else "parcial"
        detail = {
            "fuerte": f"La prueba detectó los {len(ran)} cambios a las líneas de la regla",
            "parcial": f"La prueba detectó {killed} de {len(ran)} cambios; revisa los que no notó",
            "debil": (
                f"La prueba siguió pasando con los {len(ran)} cambios: revisa si de verdad verifica lo que dice la regla "
                "(o si esas líneas no son de esta regla)"
            ),
        }[status]
        out[rid] = StrengthResult(status, detail, killed, len(ran), survivors, source)
    return out


def loads(text: str | None) -> StrengthResult | None:
    import json

    if not text:
        return None
    try:
        d = json.loads(text)
        return StrengthResult(d["status"], d["detail"], d.get("killed", 0), d.get("total", 0), [Survivor(**s) for s in d.get("survivors") or []], d.get("source", ""))
    except (ValueError, KeyError, TypeError):
        return None
