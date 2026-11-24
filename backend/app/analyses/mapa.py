"""
Mapa del proyecto (docs/PROPUESTA_REGLAS_VERIFICABLES.md §6.2): lo que el código de un backend Python tiene, leído
con `ast` y sin ejecutar nada ni llamar a la IA.

- framework (FastAPI, Flask o Django / DRF) y punto de entrada (la app, la fábrica `create_app()` o los settings);
- endpoints con método, ruta completa (prefijos de routers, blueprints e `include()`), autenticación y roles;
- esquemas de entrada y salida (Pydantic, serializers de DRF) y modelos de datos (SQLAlchemy, SQLModel, Django);
- roles (constantes `ROLES`, enums, `requiere("gerente")`, `usuario.rol == "cajero"`);
- dónde se arma la sesión de la base y el usuario actual, integraciones externas (correo, SMS, pagos, HTTP, tareas)
  y usos de la hora (`datetime.now`…);
- los fixtures de los `conftest.py` que ya tiene el repo.

Sirve de contexto para que la IA arme el arnés de pruebas sin inventar endpoints ni campos (app.projects.reglas_arnes)
y para la prueba de humo del arnés. Es heurístico: lo que no reconoce simplemente no aparece.
"""

import ast
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath

MAX_FILES = 2000
MAX_FILE_BYTES = 400 * 1024
MAX_ENDPOINTS = 500
MAX_MODELS = 200
MAX_SCHEMAS = 300
MAX_ITEMS = 100

SKIP_DIRS = {
    ".git", ".venv", "venv", "env", ".env", "node_modules", "site-packages", "__pycache__", "build", "dist", ".tox",
    ".mypy_cache", ".pytest_cache", "migrations", "alembic", "docs",
}
TEST_DIRS = {"tests", "test", "testing"}
HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")

# Nombres de constantes y clases con roles: ROLES, ROLES_PERMITIDOS, ROL_ADMIN, class Rol(Enum), UserRole…
ROLE_NAME = re.compile(r"(^|_)(rol|role)(es|s)?($|_)|(rol|role)(es|s)?$", re.IGNORECASE)
# Atributos que guardan el rol del usuario (usuario.rol, user.role, current_user.roles…)
ROLE_ATTR = {"rol", "role", "roles", "tipo_usuario", "perfil", "user_type", "group", "grupo"}
# Funciones o decoradores que revisan roles: requiere("gerente"), roles_required("admin"), has_role("x")…
ROLE_CHECK = re.compile(r"requier|require|roles?_required|has_role|tiene_rol|solo_|only_|permit|allow|^rol|^role|rol$|role$", re.IGNORECASE)
# Dependencias o decoradores de autenticación (usuario actual, token, login, permisos)
AUTH_NAME = re.compile(r"user|usuario|auth|login|token|actual|current|requier|require|permis|jwt|rol|role|admin|sesion_activa", re.IGNORECASE)
# Un rol es una palabra corta: "gerente", "almacenista", "super_admin"
ROLE_VALUE = re.compile(r"^[A-Za-z][\w-]{1,30}$")

INTEGRATIONS = {
    "smtplib": "correo", "fastapi_mail": "correo", "flask_mail": "correo", "flask_mailman": "correo", "yagmail": "correo",
    "sendgrid": "correo", "postmarker": "correo", "mailjet_rest": "correo", "django.core.mail": "correo",
    "twilio": "sms", "vonage": "sms", "nexmo": "sms", "messagebird": "sms",
    "stripe": "pagos", "mercadopago": "pagos", "paypalrestsdk": "pagos", "paypalcheckoutsdk": "pagos", "conekta": "pagos",
    "openpay": "pagos", "braintree": "pagos", "square": "pagos",
    "httpx": "http", "requests": "http", "aiohttp": "http", "urllib.request": "http", "urllib3": "http",
    "celery": "tareas", "rq": "tareas", "dramatiq": "tareas", "huey": "tareas", "apscheduler": "tareas",
    "firebase_admin": "push", "pyfcm": "push", "onesignal_sdk": "push", "pywebpush": "push",
    "boto3": "nube", "google.cloud": "nube", "azure": "nube",
}
TIME_CALLS = {
    "datetime.now", "datetime.utcnow", "datetime.today", "date.today", "time.time", "datetime.datetime.now",
    "datetime.datetime.utcnow", "datetime.datetime.today", "datetime.date.today", "timezone.now", "arrow.now",
    "arrow.utcnow", "pendulum.now", "dt.datetime.now", "dt.date.today",
}

# DRF: vistas genéricas → métodos; viewsets → acciones del router
DRF_GENERIC = {
    "ListAPIView": ("GET",), "CreateAPIView": ("POST",), "RetrieveAPIView": ("GET",), "UpdateAPIView": ("PUT", "PATCH"),
    "DestroyAPIView": ("DELETE",), "ListCreateAPIView": ("GET", "POST"), "RetrieveUpdateAPIView": ("GET", "PUT", "PATCH"),
    "RetrieveDestroyAPIView": ("GET", "DELETE"), "RetrieveUpdateDestroyAPIView": ("GET", "PUT", "PATCH", "DELETE"),
    "ListView": ("GET",), "DetailView": ("GET",), "CreateView": ("GET", "POST"), "UpdateView": ("GET", "POST"),
    "DeleteView": ("GET", "POST"), "TemplateView": ("GET",), "FormView": ("GET", "POST"), "RedirectView": ("GET",),
}
VIEWSET_ACTIONS = {
    "list": ("GET", False), "create": ("POST", False), "retrieve": ("GET", True), "update": ("PUT", True),
    "partial_update": ("PATCH", True), "destroy": ("DELETE", True),
}
VIEWSET_BASES = {
    "ModelViewSet": ("list", "create", "retrieve", "update", "partial_update", "destroy"),
    "ReadOnlyModelViewSet": ("list", "retrieve"),
}
VIEW_METHODS = ("get", "post", "put", "patch", "delete")


# ───────────────────────── Resultado ─────────────────────────


@dataclass
class Place:
    """Algo del código que el arnés necesita encontrar: `name` es "modulo:objeto" o un nombre."""

    kind: str
    name: str
    file: str
    line: int


@dataclass
class Endpoint:
    method: str
    path: str
    function: str
    file: str
    line: int
    # Pide un usuario (dependencia, decorador o permiso de autenticación)
    auth: bool = False
    roles: list[str] = field(default_factory=list)
    # Dependencias o decoradores que aplica (usuario_actual, requiere, login_required…)
    guards: list[str] = field(default_factory=list)


@dataclass
class Column:
    name: str
    type: str = ""
    # Esquemas: sin valor por defecto. Modelos: NOT NULL sin default
    required: bool = False
    unique: bool = False
    primary_key: bool = False
    foreign_key: str = ""
    default: str = ""


@dataclass
class Model:
    name: str
    table: str
    kind: str  # sqlalchemy | sqlmodel | django
    file: str
    line: int
    fields: list[Column] = field(default_factory=list)


@dataclass
class Schema:
    name: str
    kind: str  # pydantic | drf
    file: str
    line: int
    fields: list[Column] = field(default_factory=list)


@dataclass
class Integration:
    kind: str  # correo | sms | pagos | http | tareas | push | nube
    module: str
    file: str
    line: int
    # Funciones del proyecto que la usan: dónde la sustituye el arnés ("reservas.correo:_entregar")
    functions: list[str] = field(default_factory=list)


@dataclass
class TimeUse:
    call: str
    file: str
    line: int
    # "reservas.reloj:ahora": si toda la hora pasa por una función, el arnés solo sustituye esa
    function: str = ""


@dataclass
class ProjectMap:
    framework: str | None = None
    frameworks: list[str] = field(default_factory=list)
    # Paquetes y módulos de primer nivel del proyecto (lo que las pruebas pueden importar)
    packages: list[str] = field(default_factory=list)
    entry: list[Place] = field(default_factory=list)
    endpoints: list[Endpoint] = field(default_factory=list)
    schemas: list[Schema] = field(default_factory=list)
    models: list[Model] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    auth: list[Place] = field(default_factory=list)
    database: list[Place] = field(default_factory=list)
    integrations: list[Integration] = field(default_factory=list)
    time: list[TimeUse] = field(default_factory=list)
    # conftest.py del repo → sus fixtures
    fixtures: dict[str, list[str]] = field(default_factory=dict)
    # Nombres de primer nivel de cada módulo del proyecto (y sus submódulos), para revisar que el arnés no use nombres
    # que no existen (`db.select` cuando reservas/db.py no lo define). Sin los módulos dinámicos (import *, __getattr__)
    symbols: dict[str, list[str]] = field(default_factory=dict)
    files: int = 0
    warnings: list[str] = field(default_factory=list)
    # Carpeta del repo donde está el código ("" = la raíz): las pruebas y el sandbox trabajan desde ahí
    source_root: str = ""
    # Las rutas responden páginas HTML con formularios (render_template/flash de Flask, render de Django), no JSON:
    # un rechazo no llega como 4xx sino como la misma página con un aviso
    html: bool = False

    @property
    def empty(self) -> bool:
        return not self.framework and not self.endpoints and not self.models

    def to_dict(self) -> dict:
        return asdict(self)


# ───────────────────────── Utilidades de ast ─────────────────────────


def _name(node: ast.AST | None) -> str:
    """`a.b.c` de un Name/Attribute/Call (el nombre de lo que se llama); "" si es otra cosa."""
    if isinstance(node, ast.Call):
        return _name(node.func)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _last(node: ast.AST | None) -> str:
    return _name(node).rsplit(".", 1)[-1]


def _str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    # f"{API}/productos" o "a" + "b": no se puede saber sin ejecutar
    return None


def _kw(call: ast.Call, name: str) -> ast.AST | None:
    return next((k.value for k in call.keywords if k.arg == name), None)


def _bool_kw(call: ast.Call, name: str) -> bool | None:
    value = _kw(call, name)
    return value.value if isinstance(value, ast.Constant) and isinstance(value.value, bool) else None


def _unparse(node: ast.AST | None, limit: int = 80) -> str:
    if node is None:
        return ""
    try:
        text = ast.unparse(node)
    except (ValueError, TypeError, RecursionError):
        return ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


# Archivos que marcan la carpeta donde vive el código de un proyecto Python
SOURCE_MARKERS = ("requirements.txt", "pyproject.toml", "setup.py", "setup.cfg", "manage.py", "Pipfile")


WEB_FRAMEWORKS = re.compile(r"\b(fastapi|flask|django|starlette|djangorestframework)\b", re.IGNORECASE)


def _is_web(folder: Path) -> bool:
    """La carpeta declara un framework web en sus archivos de dependencias."""
    for name in SOURCE_MARKERS:
        try:
            if WEB_FRAMEWORKS.search((folder / name).read_text(encoding="utf-8", errors="replace")[:100_000]):
                return True
        except OSError:
            continue
    return False


def source_root(files: list[str], root: Path | None = None) -> str:
    """
    Carpeta del repo donde está el código ("" = la raíz). Si la raíz no tiene `requirements.txt`, `pyproject.toml` ni
    parecidos y exactamente UNA carpeta de primer nivel sí (`backend/` en un repo con frontend y backend), ese es el
    código: sus módulos se importan sin el prefijo (`from agents.x import y`, no `backend.agents.x`). Con varias
    (`api/` y `worker/`) y la carpeta del repo (`root`), se elige la única que declara un framework web; si siguen siendo
    varias, ninguna (se trabaja desde la raíz).
    """
    top = {f for f in files if "/" not in f}
    if any(m in top for m in SOURCE_MARKERS):
        return ""
    found = sorted({parts[0] for f in files if len(parts := PurePosixPath(f).parts) == 2 and parts[1] in SOURCE_MARKERS and not parts[0].startswith(".")})
    if len(found) > 1 and root is not None:
        found = [d for d in found if _is_web(root / d)]
    return found[0] if len(found) == 1 else ""


def find_source_root(root: Path) -> str:
    """Lo mismo que `source_root`, mirando la carpeta (solo el primer nivel)."""
    files: list[str] = []
    try:
        for entry in root.iterdir():
            if entry.is_file():
                files.append(entry.name)
            elif entry.is_dir() and not entry.name.startswith("."):
                files += [f"{entry.name}/{m}" for m in SOURCE_MARKERS if (entry / m).is_file()]
    except OSError:
        return ""
    return source_root(files, root)


def _module_of(path: str, prefix: str = "") -> str:
    p = PurePosixPath(path)
    parts = list(p.with_suffix("").parts)
    if prefix and parts[: len(PurePosixPath(prefix).parts)] == list(PurePosixPath(prefix).parts) and len(parts) > len(PurePosixPath(prefix).parts):
        parts = parts[len(PurePosixPath(prefix).parts):]
    if parts and parts[0] == "src" and len(parts) > 1:
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _is_test(path: str) -> bool:
    p = PurePosixPath(path)
    return (
        p.name == "conftest.py" or p.name.startswith("test_") or p.name.endswith("_test.py") or p.stem in TEST_DIRS
        or any(part in TEST_DIRS for part in p.parts[:-1])
    )


def _join(*parts: str) -> str:
    """Une prefijos y rutas de endpoint: ("/api", "/productos", "") → "/api/productos"."""
    out = ""
    for part in parts:
        if not part:
            continue
        out = out.rstrip("/") + "/" + part.lstrip("/") if out else part
    if not out.startswith("/"):
        out = "/" + out
    return out


FLASK_PARAM = re.compile(r"<(?:[^:<>]+:)?([^<>]+)>")


def _normalize(path: str) -> str:
    """Parámetros al estilo de FastAPI: Flask `<int:id>` y Django `<int:pk>` → `{id}` / `{pk}`."""
    return FLASK_PARAM.sub(r"{\1}", path)


# ───────────────────────── Lectura por módulo ─────────────────────────


@dataclass
class _Module:
    path: str
    name: str
    tree: ast.Module
    is_test: bool
    # alias → (módulo, nombre importado o None si se importó el módulo)
    imports: dict[str, tuple[str, str | None]] = field(default_factory=dict)
    # Constantes de texto de primer nivel: NOMBRE → valores
    constants: dict[str, list[str]] = field(default_factory=dict)
    # Annotated[T, Depends(f)] de primer nivel: alias → dependencias
    annotated: dict[str, list[str]] = field(default_factory=dict)
    # Variables con una app o un router: nombre → (tipo, prefijo, dependencias del router)
    routers: dict[str, tuple[str, str, list[str]]] = field(default_factory=dict)
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = field(default_factory=dict)
    classes: dict[str, ast.ClassDef] = field(default_factory=dict)


def _resolve_import(module: str, node: ast.ImportFrom, is_package: bool) -> str:
    if not node.level:
        return node.module or ""
    base = module.split(".") if module else []
    # En un __init__.py el nivel 1 es el propio paquete
    drop = node.level - 1 if is_package else node.level
    base = base[: len(base) - drop] if drop else base
    return ".".join([*base, *([node.module] if node.module else [])])


def _strings(node: ast.AST | None, constants: dict[str, list[str]]) -> list[str]:
    """Textos de un literal ("a", ("a", "b"), [...], {...}) o de una constante ya conocida."""
    if node is None:
        return []
    value = _str(node)
    if value is not None:
        return [value]
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return [s for elt in node.elts for s in _strings(elt, constants)]
    if isinstance(node, ast.Name) and node.id in constants:
        return constants[node.id]
    if isinstance(node, ast.Starred):
        return _strings(node.value, constants)
    if isinstance(node, ast.Attribute) and _is_role_name(node.attr):
        # Rol.GERENTE de un enum: el valor se resuelve después con los enums
        return [f"@enum:{node.attr}"]
    return []


def _is_role_name(name: str) -> bool:
    return bool(ROLE_NAME.search(name)) or name.isupper()


# Python 3.14 (PEP 758) acepta `except A, B:` sin paréntesis; el backend (3.12) no lo puede leer
BARE_EXCEPT = re.compile(r"^(\s*except\*?\s+)([^():\n#]+,[^():\n#]+?)(\s*:)", re.MULTILINE)


def _parse(source: str, path: str) -> ast.Module | None:
    try:
        return ast.parse(source, filename=path)
    except (SyntaxError, ValueError, RecursionError):
        pass
    fixed = BARE_EXCEPT.sub(r"\1(\2)\3", source)
    if fixed == source:
        return None
    try:
        return ast.parse(fixed, filename=path)
    except (SyntaxError, ValueError, RecursionError):
        return None


def _read_module(path: str, source: str, prefix: str = "") -> _Module | None:
    tree = _parse(source, path)
    if tree is None:
        return None
    m = _Module(path, _module_of(path, prefix), tree, _is_test(path))
    is_package = PurePosixPath(path).name == "__init__.py"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                m.imports[a.asname or a.name.split(".")[0]] = (a.name if a.asname else a.name.split(".")[0], None)
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_import(m.name, node, is_package)
            for a in node.names:
                m.imports[a.asname or a.name] = (base, a.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            m.functions.setdefault(node.name, node)
        elif isinstance(node, ast.ClassDef):
            m.classes.setdefault(node.name, node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Call):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            kind = _last(node.value.func)
            for t in targets:
                if not isinstance(t, ast.Name):
                    continue
                if kind in ("FastAPI", "APIRouter"):
                    deps = _depends_in(_kw(node.value, "dependencies"), {})
                    m.routers[t.id] = (kind, _str(_kw(node.value, "prefix")) or "", deps)
                elif kind == "Flask":
                    m.routers[t.id] = ("Flask", "", [])
                elif kind == "Blueprint":
                    m.routers[t.id] = ("Blueprint", _str(_kw(node.value, "url_prefix")) or "", [])
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            for t in targets:
                if not isinstance(t, ast.Name) or value is None:
                    continue
                strings = _strings(value, m.constants)
                if strings and not any(s.startswith("@enum:") for s in strings):
                    m.constants[t.id] = strings
                if isinstance(value, ast.Subscript) and _last(value.value) == "Annotated":
                    m.annotated[t.id] = _depends_in(value.slice, {})
    return m


def _depends_in(node: ast.AST | None, annotated: dict[str, list[str]]) -> list[str]:
    """Nombres de las dependencias en Depends(f) / Security(f) dentro de `node` (también de alias Annotated)."""
    found: list[str] = []
    if node is None:
        return found
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and _last(sub.func) in ("Depends", "Security") and sub.args:
            found.append(_name(sub.args[0]))
        elif isinstance(sub, ast.Name) and sub.id in annotated:
            found += annotated[sub.id]
    return [f for f in found if f]


# ───────────────────────── El mapa ─────────────────────────


class _Builder:
    def __init__(self, modules: list[_Module]):
        self.modules = modules
        self.by_name = {m.name: m for m in modules}
        self.map = ProjectMap()
        self.enum_roles: dict[str, str] = {}
        self.role_values: set[str] = set()

    # ─── Resolución entre módulos ───

    def constant(self, m: _Module, name: str) -> list[str]:
        if name in m.constants:
            return m.constants[name]
        if name in m.imports:
            mod, attr = m.imports[name]
            other = self.by_name.get(mod)
            if other and attr and attr in other.constants:
                return other.constants[attr]
        return []

    def imported_alias(self, m: _Module, name: str) -> list[str]:
        if name not in m.imports:
            return []
        mod, attr = m.imports[name]
        other = self.by_name.get(mod)
        return other.annotated.get(attr, []) if other and attr else []

    def strings(self, m: _Module, node: ast.AST | None) -> list[str]:
        if isinstance(node, ast.Starred):
            node = node.value
        if isinstance(node, ast.Name) and node.id not in m.constants:
            return self.constant(m, node.id)
        return _strings(node, m.constants)

    def definition(self, m: _Module, name: str) -> tuple[_Module, ast.AST] | None:
        """Dónde está definida la función o clase `name` vista desde `m` (sigue un nivel de import)."""
        head = name.split(".")[0]
        if "." not in name:
            if name in m.functions:
                return m, m.functions[name]
            if name in m.classes:
                return m, m.classes[name]
        if head in m.imports:
            mod, attr = m.imports[head]
            target_mod = mod if attr is None else mod if "." not in name else f"{mod}.{attr}"
            target = name.split(".")[-1] if "." in name else attr or ""
            other = self.by_name.get(target_mod) or self.by_name.get(mod)
            if other:
                node = other.functions.get(target) or other.classes.get(target)
                if node is not None:
                    return other, node
        return None

    def router_key(self, m: _Module, var: str) -> tuple[str, str] | None:
        """(módulo, variable) del router o app `var` usado en `m`: propio o importado (`from app.main import bp`)."""
        if var in m.routers:
            return m.name, var
        if var in m.imports:
            mod, attr = m.imports[var]
            if attr and mod in self.by_name and attr in self.by_name[mod].routers:
                return mod, attr
        return None

    def anywhere(self, name: str) -> tuple[_Module, ast.AST] | None:
        """La función `name` si un solo módulo del proyecto (fuera de las pruebas) la define."""
        found = [(m, m.functions[name]) for m in self.modules if not m.is_test and name in m.functions]
        return found[0] if len(found) == 1 else None

    def router_ref(self, m: _Module, node: ast.AST) -> tuple[str, str] | None:
        """(módulo, variable) del router que se incluye: `productos`, `rutas.router`, `api.v1.router`."""
        if isinstance(node, ast.Name):
            if node.id in m.routers:
                return m.name, node.id
            if node.id in m.imports:
                mod, attr = m.imports[node.id]
                if attr:
                    if mod in self.by_name and attr in self.by_name[mod].routers:
                        return mod, attr
                    return f"{mod}.{attr}", "router"
                return mod, "router"
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in m.imports:
            mod, attr = m.imports[node.value.id]
            return (f"{mod}.{attr}" if attr else mod), node.attr
        return None

    # ─── Routers y prefijos (FastAPI y Flask) ───

    def prefixes(self) -> dict[tuple[str, str], tuple[str, list[str]]]:
        """(módulo, variable) → (prefijo completo, dependencias heredadas)."""
        own = {(m.name, var): info for m in self.modules for var, info in m.routers.items()}
        parent: dict[tuple[str, str], tuple[tuple[str, str], str, list[str]]] = {}
        for m in self.modules:
            for node in ast.walk(m.tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.args):
                    continue
                if node.func.attr not in ("include_router", "register_blueprint"):
                    continue
                child = self.router_ref(m, node.args[0])
                host = node.func.value
                if child is None or not isinstance(host, ast.Name) or host.id not in m.routers:
                    continue
                prefix = _str(_kw(node, "prefix" if node.func.attr == "include_router" else "url_prefix")) or ""
                parent.setdefault(child, ((m.name, host.id), prefix, _depends_in(_kw(node, "dependencies"), m.annotated)))

        memo: dict[tuple[str, str], tuple[str, list[str]]] = {}

        def full(key: tuple[str, str], seen: frozenset = frozenset()) -> tuple[str, list[str]]:
            if key in memo:
                return memo[key]
            _, prefix, deps = own.get(key, ("", "", []))
            if key in parent and key not in seen:
                (host, include_prefix, include_deps) = parent[key]
                base, base_deps = full(host, seen | {key})
                result = (_join(base, include_prefix, prefix) if (base or include_prefix or prefix) else "", [*base_deps, *include_deps, *deps])
            else:
                result = (prefix, list(deps))
            memo[key] = result
            return result

        return {key: full(key) for key in own}

    # ─── Roles y autenticación de un endpoint ───

    def guards_of(self, m: _Module, fn: ast.FunctionDef | ast.AsyncFunctionDef, extra: list[ast.AST]) -> tuple[list[str], list[str]]:
        """(guardias: dependencias y decoradores, roles que exigen)."""
        guards: list[str] = []
        roles: list[str] = []
        nodes: list[ast.AST] = [*fn.decorator_list, *extra]
        args = fn.args
        for a in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
            if a.annotation is not None:
                nodes.append(a.annotation)
        nodes += [d for d in [*args.defaults, *args.kw_defaults] if d is not None]
        for node in nodes:
            guards += _depends_in(node, m.annotated)
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and sub.id not in m.annotated:
                    # Alias Annotated importado de otro módulo (Actual = Annotated[Usuario, Depends(usuario_actual)])
                    guards += self.imported_alias(m, sub.id)
                if isinstance(sub, ast.Call) and ROLE_CHECK.search(_last(sub.func)):
                    for arg in sub.args:
                        roles += self.strings(m, arg)
                    guards.append(_name(sub.func))
                elif isinstance(sub, (ast.Name, ast.Attribute)) and node in fn.decorator_list and sub is node:
                    guards.append(_name(sub))
            if isinstance(node, ast.Call) and node in fn.decorator_list:
                guards.append(_name(node.func))
        roles += self.inline_roles(m, fn)
        # El decorador de la ruta (@app.get, @router.post, @bp.route) no es una guardia
        route = {*HTTP_METHODS, "route", "api_route", "websocket"}
        return list(dict.fromkeys(g for g in guards if g and _last_name(g) not in route)), list(dict.fromkeys(r for r in roles if r))

    def inline_roles(self, m: _Module, fn: ast.AST) -> list[str]:
        """
        `usuario.rol == "gerente"`, `user.role in ("a", "b")`, `if rol != Rol.ADMIN` dentro del cuerpo, y los grupos de
        Django como roles: `user.groups.filter(name="almacen")`, `Group.objects.get(name="gerente")`.
        """
        roles: list[str] = []
        for sub in ast.walk(fn):
            if isinstance(sub, ast.Call) and _last(sub.func) in ("filter", "get", "exclude") and re.search(r"(^|\.)(groups|Group)(\.|$)", _name(sub.func)):
                roles += self.strings(m, _kw(sub, "name") or _kw(sub, "name__in"))
            if not isinstance(sub, ast.Compare):
                continue
            sides = [sub.left, *sub.comparators]
            if not any(isinstance(s, ast.Attribute) and s.attr.lower() in ROLE_ATTR for s in sides):
                continue
            for s in sides:
                if not (isinstance(s, ast.Attribute) and s.attr.lower() in ROLE_ATTR):
                    roles += self.strings(m, s)
        return roles

    def is_auth(self, guards: list[str]) -> bool:
        return any(AUTH_NAME.search(g.rsplit(".", 1)[-1]) and not re.search(r"(^|_)(db|session|sesion)$", g, re.IGNORECASE) for g in guards)

    # ─── FastAPI y Flask ───

    def web_endpoints(self) -> None:
        prefixes = self.prefixes()
        for m in self.modules:
            if m.is_test:
                continue
            for fn in ast.walk(m.tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for dec in fn.decorator_list:
                    if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and isinstance(dec.func.value, ast.Name)):
                        continue
                    var, attr = dec.func.value.id, dec.func.attr
                    if attr not in (*HTTP_METHODS, "route", "api_route", "websocket"):
                        continue
                    key = self.router_key(m, var)
                    if key is None:
                        continue
                    info = self.by_name[key[0]].routers[key[1]]
                    kind = info[0]
                    path = _str(dec.args[0]) if dec.args else _str(_kw(dec, "path") or _kw(dec, "rule"))
                    if path is None:
                        continue
                    if attr in ("route", "api_route"):
                        methods = [s.upper() for s in self.strings(m, _kw(dec, "methods"))] or ["GET"]
                    elif attr == "websocket":
                        methods = ["WS"]
                    else:
                        methods = [attr.upper()]
                    prefix, router_deps = prefixes.get(key, ("", []))
                    extra = [d for d in [_kw(dec, "dependencies")] if d is not None]
                    guards, roles = self.guards_of(m, fn, extra)
                    guards = list(dict.fromkeys([*router_deps, *guards]))
                    full = _normalize(_join(prefix, path)) if kind in ("Flask", "Blueprint") else _join(prefix, path)
                    for method in methods:
                        self.map.endpoints.append(Endpoint(method, full, f"{m.name}:{fn.name}", m.path, fn.lineno, self.is_auth(guards), roles, guards))

    # ─── Django / DRF ───

    def django_endpoints(self) -> None:
        urlconfs = [m for m in self.modules if "urlpatterns" in {t.id for n in m.tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}]
        if not urlconfs:
            return
        root_name = None
        for m in self.modules:
            for node in m.tree.body:
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "ROOT_URLCONF" for t in node.targets):
                    root_name = _str(node.value)
        included = {s for m in urlconfs for node in ast.walk(m.tree) if isinstance(node, ast.Call) and _last(node.func) == "include" for s in [_str(node.args[0]) if node.args else None] if s}
        roots = [self.by_name[root_name]] if root_name in self.by_name else [m for m in urlconfs if m.name not in included]
        seen: set[str] = set()
        for root in roots:
            self.urlconf(root, "", seen)

    def urlconf(self, m: _Module, prefix: str, seen: set[str]) -> None:
        if m.name in seen or len(self.map.endpoints) >= MAX_ENDPOINTS:
            return
        seen.add(m.name)
        routers: dict[str, list[tuple[str, ast.AST]]] = {}
        for node in ast.walk(m.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "register" and len(node.args) >= 2:
                base = _str(node.args[0])
                if base is not None and isinstance(node.func.value, ast.Name):
                    routers.setdefault(node.func.value.id, []).append((base, node.args[1]))
        patterns = next((n.value for n in m.tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "urlpatterns" for t in n.targets)), None)
        # urlpatterns = [...] + router.urls
        entries: list[ast.AST] = []
        for sub in ast.walk(patterns) if patterns is not None else []:
            if isinstance(sub, ast.List):
                entries += sub.elts
            elif isinstance(sub, ast.Attribute) and sub.attr == "urls" and isinstance(sub.value, ast.Name) and sub.value.id in routers:
                self.drf_router(m, prefix, routers[sub.value.id])
        for entry in entries:
            if not (isinstance(entry, ast.Call) and _last(entry.func) in ("path", "re_path", "url") and len(entry.args) >= 2):
                continue
            route = _str(entry.args[0])
            if route is None:
                continue
            route = route.lstrip("^").rstrip("$") if _last(entry.func) != "path" else route
            target = entry.args[1]
            here = _join(prefix, route)
            if isinstance(target, ast.Call) and _last(target.func) == "include":
                inc = target.args[0] if target.args else None
                if isinstance(inc, ast.Attribute) and inc.attr == "urls" and isinstance(inc.value, ast.Name) and inc.value.id in routers:
                    self.drf_router(m, here, routers[inc.value.id])
                elif _str(inc) in self.by_name:
                    self.urlconf(self.by_name[_str(inc)], here, seen)
                elif isinstance(inc, (ast.Tuple, ast.List)) and inc.elts and _str(inc.elts[0]) in self.by_name:
                    self.urlconf(self.by_name[_str(inc.elts[0])], here, seen)
                continue
            self.django_view(m, _normalize(here), target)

    def drf_router(self, m: _Module, prefix: str, registered: list[tuple[str, ast.AST]]) -> None:
        for base, view in registered:
            found = self.definition(m, _name(view))
            if not found or not isinstance(found[1], ast.ClassDef):
                continue
            vm, cls = found
            bases = {_last(b) for b in cls.bases}
            defined = {n.name for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
            actions = [a for b in bases for a in VIEWSET_BASES.get(b, ())] + [a for a in VIEWSET_ACTIONS if a in defined]
            guards, roles, auth = self.class_guards(vm, cls)
            root = _join(prefix, base)
            for action in dict.fromkeys(actions):
                method, detail = VIEWSET_ACTIONS[action]
                path = _join(root, "{pk}") + "/" if detail else root.rstrip("/") + "/"
                self.map.endpoints.append(Endpoint(method, path, f"{vm.name}:{cls.name}.{action}", vm.path, cls.lineno, auth, roles, guards))
            for n in cls.body:
                if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                dec = next((d for d in n.decorator_list if isinstance(d, ast.Call) and _last(d.func) == "action"), None)
                if dec is None:
                    continue
                detail = _bool_kw(dec, "detail")
                url = _str(_kw(dec, "url_path")) or n.name
                path = (_join(root, "{pk}", url) if detail else _join(root, url)) + "/"
                for method in [s.upper() for s in self.strings(vm, _kw(dec, "methods"))] or ["GET"]:
                    self.map.endpoints.append(Endpoint(method, path, f"{vm.name}:{cls.name}.{n.name}", vm.path, n.lineno, auth, roles + self.inline_roles(vm, n), guards))

    def class_guards(self, m: _Module, cls: ast.ClassDef) -> tuple[list[str], list[str], bool]:
        """(guardias, roles, pide usuario). Cualquier `permission_classes` que no sea AllowAny pide un usuario."""
        guards: list[str] = []
        roles: list[str] = []
        permissions = False
        for n in cls.body:
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ("permission_classes", "authentication_classes") for t in n.targets):
                for elt in getattr(n.value, "elts", []):
                    if _last(elt) != "AllowAny":
                        guards.append(_name(elt))
                        permissions = True
        for dec in cls.decorator_list:
            guards.append(_name(dec))
        guards = [g for g in guards if g]
        for g in guards:
            found = self.definition(m, g)
            if found:
                roles += self.inline_roles(*found)
        roles += self.inline_roles(m, cls)
        return list(dict.fromkeys(guards)), list(dict.fromkeys(roles)), permissions or self.is_auth(guards)

    def django_view(self, m: _Module, path: str, target: ast.AST) -> None:
        view = target.func.value if isinstance(target, ast.Call) and isinstance(target.func, ast.Attribute) and target.func.attr == "as_view" else target
        found = self.definition(m, _name(view))
        if not found:
            return
        vm, node = found
        if isinstance(node, ast.ClassDef):
            bases = {_last(b) for b in node.bases}
            defined = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in VIEW_METHODS]
            methods = [mm for b in bases for mm in DRF_GENERIC.get(b, ())] + [d.upper() for d in defined]
            guards, roles, auth = self.class_guards(vm, node)
            for method in dict.fromkeys(methods or ["GET"]):
                self.map.endpoints.append(Endpoint(method, path, f"{vm.name}:{node.name}", vm.path, node.lineno, auth, roles, guards))
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            dec = next((d for d in node.decorator_list if isinstance(d, ast.Call) and _last(d.func) in ("api_view", "require_http_methods")), None)
            methods = [s.upper() for s in self.strings(vm, dec.args[0])] if dec is not None and dec.args else []
            if not methods:
                methods = [{"require_GET": "GET", "require_POST": "POST"}[_last(d)] for d in node.decorator_list if _last(d) in ("require_GET", "require_POST")] or ["GET"]
            guards, roles = self.guards_of(vm, node, [])
            for method in methods:
                self.map.endpoints.append(Endpoint(method, path, f"{vm.name}:{node.name}", vm.path, node.lineno, self.is_auth(guards), roles, guards))

    # ─── Modelos y esquemas ───

    def models_and_schemas(self) -> None:
        classes = [(m, c) for m in self.modules if not m.is_test for c in ast.walk(m.tree) if isinstance(c, ast.ClassDef)]
        names = {c.name: {_last(b) for b in c.bases} for _, c in classes}
        by_class = {c.name: c for _, c in classes}
        # Bases declarativas de SQLAlchemy: class Base(DeclarativeBase), Base = declarative_base(), db = SQLAlchemy() → db.Model
        declarative = {n for n, bases in names.items() if bases & {"DeclarativeBase", "DeclarativeBaseNoMeta"}}
        flask_db: set[str] = set()
        for m in self.modules:
            for node in m.tree.body:
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and _last(node.value.func) in ("declarative_base", "SQLAlchemy"):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            (declarative if _last(node.value.func) == "declarative_base" else flask_db).add(t.id)
        django_roots = {c.name for _, c in classes if any(_name(b).endswith("models.Model") for b in c.bases)}
        django = django_roots | self._closure(names, django_roots)
        sa_roots = {c.name for _, c in classes if {_last(b) for b in c.bases} & declarative or any(_name(b) in {f"{d}.Model" for d in flask_db} for b in c.bases)}
        sqlalchemy = sa_roots | self._closure(names, sa_roots)
        sqlmodel = self._closure(names, {"SQLModel"})
        pydantic = self._closure(names, {"BaseModel", "RootModel"})
        drf = self._closure(names, {"Serializer", "ModelSerializer", "HyperlinkedModelSerializer"})

        def inherited(cls: ast.ClassDef, read, stop: set[str], seen: frozenset = frozenset()) -> list[Column]:
            """Campos de las clases base del proyecto (SQLModel, mixins, abstractas) y después los propios."""
            fields: dict[str, Column] = {}
            for b in cls.bases:
                base = by_class.get(_last(b))
                if base is not None and base.name not in stop and base.name not in seen and base is not cls:
                    for col in inherited(base, read, stop, seen | {cls.name}):
                        fields[col.name] = col
            for col in read(cls):
                fields[col.name] = col
            return list(fields.values())

        for m, cls in classes:
            table = next((_str(n.value) for n in cls.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__tablename__" for t in n.targets)), None)
            is_table = any(k.arg == "table" and isinstance(k.value, ast.Constant) and k.value.value for k in cls.keywords)
            if cls.name in sqlmodel:
                if is_table and len(self.map.models) < MAX_MODELS:
                    self.map.models.append(Model(cls.name, table or cls.name.lower(), "sqlmodel", m.path, cls.lineno, inherited(cls, self._sa_fields, {"SQLModel"})))
                elif not is_table and len(self.map.schemas) < MAX_SCHEMAS:
                    self.map.schemas.append(Schema(cls.name, "pydantic", m.path, cls.lineno, inherited(cls, self._pydantic_fields, {"SQLModel"})))
            elif cls.name in django:
                if not self._abstract(cls) and len(self.map.models) < MAX_MODELS:
                    self.map.models.append(Model(cls.name, cls.name.lower(), "django", m.path, cls.lineno, inherited(cls, self._django_fields, set())))
            elif cls.name in sqlalchemy or table is not None:
                if cls.name not in declarative and not self._abstract(cls) and len(self.map.models) < MAX_MODELS:
                    self.map.models.append(Model(cls.name, table or cls.name.lower(), "sqlalchemy", m.path, cls.lineno, inherited(cls, self._sa_fields, declarative)))
            elif cls.name in pydantic and "BaseSettings" not in names[cls.name]:
                if len(self.map.schemas) < MAX_SCHEMAS:
                    self.map.schemas.append(Schema(cls.name, "pydantic", m.path, cls.lineno, inherited(cls, self._pydantic_fields, {"BaseModel"})))
            elif cls.name in drf and len(self.map.schemas) < MAX_SCHEMAS:
                self.map.schemas.append(Schema(cls.name, "drf", m.path, cls.lineno, self._drf_fields(cls)))

    @staticmethod
    def _closure(names: dict[str, set[str]], roots: set[str]) -> set[str]:
        found = set()
        changed = True
        while changed:
            changed = False
            for name, bases in names.items():
                if name not in found and bases & (roots | found):
                    found.add(name)
                    changed = True
        return found

    @staticmethod
    def _abstract(node: ast.ClassDef) -> bool:
        for n in node.body:
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__abstract__" for t in n.targets):
                return True
            if isinstance(n, ast.ClassDef) and n.name == "Meta":
                for s in n.body:
                    if isinstance(s, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "abstract" for t in s.targets):
                        return True
        return False

    @staticmethod
    def _sa_fields(node: ast.ClassDef) -> list[Column]:
        out: list[Column] = []
        for n in node.body:
            target = n.target if isinstance(n, ast.AnnAssign) else n.targets[0] if isinstance(n, ast.Assign) and len(n.targets) == 1 else None
            if not isinstance(target, ast.Name) or target.id.startswith("__"):
                continue
            call = n.value if isinstance(n.value, ast.Call) else None
            func = _last(call.func) if call else ""
            if func in ("relationship", "Relationship", "association_proxy", "hybrid_property"):
                continue
            annotation = n.annotation if isinstance(n, ast.AnnAssign) else None
            if func not in ("mapped_column", "Column", "Field") and not (annotation is not None and _last(annotation) == "Mapped" or annotation is not None and isinstance(n, ast.AnnAssign)):
                continue
            col = Column(target.id)
            if isinstance(annotation, ast.Subscript) and _last(annotation.value) == "Mapped":
                col.type = _unparse(annotation.slice)
            elif annotation is not None:
                col.type = _unparse(annotation)
            if call:
                for arg in call.args:
                    if _last(arg) == "ForeignKey" and isinstance(arg, ast.Call) and arg.args:
                        col.foreign_key = _str(arg.args[0]) or _unparse(arg.args[0])
                    elif not col.type or func == "Column":
                        col.type = col.type or _unparse(arg)
                col.unique = bool(_bool_kw(call, "unique"))
                col.primary_key = bool(_bool_kw(call, "primary_key"))
                default = _kw(call, "default") or _kw(call, "server_default")
                col.default = _unparse(default)
                if func == "Field":
                    fk = _kw(call, "foreign_key")
                    col.foreign_key = _str(fk) or ""
                nullable = _bool_kw(call, "nullable")
                optional = "None" in col.type or "Optional" in col.type
                col.required = not col.primary_key and default is None and (nullable is False or (nullable is None and not optional))
            else:
                col.required = "None" not in col.type and "Optional" not in col.type
            out.append(col)
        return out

    @staticmethod
    def _django_fields(node: ast.ClassDef) -> list[Column]:
        out: list[Column] = []
        for n in node.body:
            if not (isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Call)):
                continue
            func = _last(n.value.func)
            if not (func.endswith("Field") or func in ("ForeignKey", "OneToOneField", "ManyToManyField")):
                continue
            call = n.value
            col = Column(n.targets[0].id, func)
            col.unique = bool(_bool_kw(call, "unique"))
            col.primary_key = bool(_bool_kw(call, "primary_key"))
            col.default = _unparse(_kw(call, "default"))
            if func in ("ForeignKey", "OneToOneField", "ManyToManyField") and call.args:
                col.foreign_key = _str(call.args[0]) or _unparse(call.args[0])
            col.required = not _bool_kw(call, "null") and not _bool_kw(call, "blank") and _kw(call, "default") is None and not col.primary_key
            out.append(col)
        return out

    @staticmethod
    def _pydantic_fields(node: ast.ClassDef) -> list[Column]:
        out: list[Column] = []
        for n in node.body:
            if not (isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)) or n.target.id.startswith("_") or n.target.id == "model_config":
                continue
            if _last(n.annotation) == "ClassVar":
                continue
            value = n.value
            required = value is None
            default = ""
            if isinstance(value, ast.Call) and _last(value.func) == "Field":
                first = value.args[0] if value.args else _kw(value, "default")
                required = (first is None or (isinstance(first, ast.Constant) and first.value is Ellipsis)) and _kw(value, "default_factory") is None
                default = "" if required else _unparse(first or _kw(value, "default_factory"))
            elif value is not None:
                default = _unparse(value)
            out.append(Column(n.target.id, _unparse(n.annotation), required=required, default=default))
        return out

    @staticmethod
    def _drf_fields(node: ast.ClassDef) -> list[Column]:
        out: list[Column] = []
        for n in node.body:
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Call):
                func = _last(n.value.func)
                if func.endswith(("Field", "Serializer")):
                    out.append(Column(n.targets[0].id, func, required=_bool_kw(n.value, "required") is not False and not _bool_kw(n.value, "read_only")))
            if isinstance(n, ast.ClassDef) and n.name == "Meta":
                for s in n.body:
                    if isinstance(s, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "fields" for t in s.targets):
                        names = _strings(s.value, {})
                        out += [Column(f) for f in names if f != "__all__" and f not in {c.name for c in out}]
        return out

    # ─── Roles del proyecto ───

    def roles(self) -> None:
        values: list[str] = []
        for m in self.modules:
            if m.is_test:
                continue
            for name, strings in m.constants.items():
                if ROLE_NAME.search(name):
                    values += strings
            for cls in m.classes.values():
                bases = {_last(b) for b in cls.bases}
                if not (bases & {"Enum", "StrEnum", "TextChoices", "IntEnum"}):
                    continue
                for n in cls.body:
                    if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                        v = _str(n.value) or (_str(n.value.elts[0]) if isinstance(n.value, ast.Tuple) and n.value.elts else None)
                        if v is not None:
                            self.enum_roles[n.targets[0].id] = v
                            if ROLE_NAME.search(cls.name):
                                values.append(v)
        for e in self.map.endpoints:
            values += e.roles
        for model in self.map.models:
            for col in model.fields:
                if col.name.lower() in ROLE_ATTR and col.default:
                    try:
                        literal = ast.literal_eval(col.default)
                    except (ValueError, SyntaxError):
                        literal = None
                    if isinstance(literal, str):
                        values.append(literal)
        # Rol.GERENTE → "gerente" (si el enum se conoce)
        resolved = [self.enum_roles.get(v.removeprefix("@enum:"), "") if v.startswith("@enum:") else v for v in values]
        for e in self.map.endpoints:
            e.roles = list(dict.fromkeys(r for r in (self.enum_roles.get(v.removeprefix("@enum:"), "") if v.startswith("@enum:") else v for v in e.roles) if ROLE_VALUE.match(r)))
        self.map.roles = list(dict.fromkeys(r for r in resolved if ROLE_VALUE.match(r)))[:MAX_ITEMS]

    # ─── Autenticación, base de datos, integraciones, hora, entrada ───

    def places(self) -> None:
        mp = self.map
        guards = {g for e in mp.endpoints for g in e.guards}
        seen_auth: set[str] = set()
        for e in mp.endpoints:
            m = next((x for x in self.modules if x.path == e.file), None)
            if m is None:
                continue
            for g in e.guards:
                if g in seen_auth or not self.is_auth([g]):
                    continue
                seen_auth.add(g)
                found = self.definition(m, g) or self.anywhere(g)
                if found:
                    dm, node = found
                    mp.auth.append(Place("guardia", f"{dm.name}:{getattr(node, 'name', g)}", dm.path, node.lineno))
                else:
                    mp.auth.append(Place("guardia", g, "", 0))
        for m in self.modules:
            if m.is_test:
                continue
            for node in ast.walk(m.tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yields = any(isinstance(s, (ast.Yield, ast.YieldFrom)) for s in ast.walk(node))
                    if (yields and re.search(r"db|session|sesion|conn", node.name, re.IGNORECASE)) or node.name in guards and re.search(r"(^|_)(db|session|sesion)$", node.name):
                        mp.database.append(Place("sesion", f"{m.name}:{node.name}", m.path, node.lineno))
                elif isinstance(node, ast.Call):
                    func = _last(node.func)
                    if func in ("create_engine", "create_async_engine", "sessionmaker", "async_sessionmaker", "scoped_session"):
                        # La base REAL del proyecto: `engine = create_engine(URL)`, `SessionLocal = sessionmaker(...)`. El
                        # arnés no debe usarla (app.projects.reglas_arnes.validate avisa)
                        kind = "engine" if "engine" in func else "fabrica"
                        target = self._assigned(m, node)
                        where = target if target and any(isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value is node for n in m.tree.body) else f"{self._enclosing(m, node) or func}()"
                        mp.database.append(Place(kind, f"{m.name}:{where}", m.path, node.lineno))
                    elif func == "SQLAlchemy" and _name(node.func) in ("SQLAlchemy", "flask_sqlalchemy.SQLAlchemy"):
                        mp.database.append(Place("flask_sqlalchemy", f"{m.name}:SQLAlchemy", m.path, node.lineno))
                    elif func == "FastAPI":
                        target = self._assigned(m, node)
                        mp.entry.append(Place("app", f"{m.name}:{target or 'app'}", m.path, node.lineno))
                    elif func == "Flask":
                        factory = self._enclosing(m, node)
                        if factory:
                            mp.entry.append(Place("factory", f"{m.name}:{factory}", m.path, node.lineno))
                        else:
                            mp.entry.append(Place("app", f"{m.name}:{self._assigned(m, node) or 'app'}", m.path, node.lineno))
                    elif func == "setdefault" and node.args and _str(node.args[0]) == "DJANGO_SETTINGS_MODULE" and len(node.args) > 1:
                        mp.entry.append(Place("settings", _str(node.args[1]) or "", m.path, node.lineno))
                elif isinstance(node, ast.ClassDef) and {_last(b) for b in node.bases} & {"DeclarativeBase", "DeclarativeBaseNoMeta"}:
                    mp.database.append(Place("base", f"{m.name}:{node.name}", m.path, node.lineno))
                elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ("DATABASES", "SQLALCHEMY_DATABASE_URI") for t in node.targets):
                    mp.database.append(Place("config", f"{m.name}:{node.targets[0].id}", m.path, node.lineno))
            self.integrations(m)
            self.time_uses(m)
        # manage.py, wsgi.py y asgi.py apuntan a los mismos settings
        mp.entry = list({(p.kind, p.name): p for p in reversed(mp.entry)}.values())[::-1][:MAX_ITEMS]
        mp.database = _unique(mp.database)[:MAX_ITEMS]
        mp.auth = _unique(mp.auth)[:MAX_ITEMS]

    @staticmethod
    def _assigned(m: _Module, call: ast.Call) -> str:
        for node in ast.walk(m.tree):
            if isinstance(node, ast.Assign) and node.value is call:
                t = node.targets[0]
                return t.id if isinstance(t, ast.Name) else ""
            if isinstance(node, ast.AnnAssign) and node.value is call and isinstance(node.target, ast.Name):
                return node.target.id
        return ""

    @staticmethod
    def _enclosing(m: _Module, target: ast.AST) -> str:
        for node in ast.walk(m.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(sub is target for sub in ast.walk(node)):
                return node.name
        return ""

    def integrations(self, m: _Module) -> None:
        for alias, (mod, attr) in m.imports.items():
            full = f"{mod}.{attr}" if attr else mod
            kind = next((k for prefix, k in INTEGRATIONS.items() if full == prefix or full.startswith(prefix + ".") or mod == prefix), None)
            if kind is None:
                continue
            line = next((n.lineno for n in ast.walk(m.tree) if isinstance(n, (ast.Import, ast.ImportFrom)) and any((a.asname or a.name.split(".")[0]) == alias for a in n.names)), 1)
            users = [
                f"{m.name}:{fn.name}" for fn in ast.walk(m.tree)
                if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(isinstance(s, ast.Name) and s.id == alias for s in ast.walk(fn))
            ]
            self.map.integrations.append(Integration(kind, full, m.path, line, list(dict.fromkeys(users))[:10]))

    def time_uses(self, m: _Module) -> None:
        stack: list[str] = []

        def visit(node: ast.AST) -> None:
            is_fn = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            if is_fn:
                stack.append(node.name)
            if isinstance(node, ast.Call) and _name(node.func) in TIME_CALLS and len(self.map.time) < MAX_ITEMS:
                self.map.time.append(TimeUse(_name(node.func), m.path, node.lineno, f"{m.name}:{stack[-1]}" if stack else m.name))
            for child in ast.iter_child_nodes(node):
                visit(child)
            if is_fn:
                stack.pop()

        visit(m.tree)

    def symbols(self) -> None:
        names = {m.name for m in self.modules}
        for m in self.modules:
            if m.is_test or not m.name:
                continue
            body = m.tree.body
            if any(isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names) for n in body) or "__getattr__" in m.functions:
                continue
            found: list[str] = []
            for n in body:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    found.append(n.name)
                elif isinstance(n, (ast.Assign, ast.AnnAssign)):
                    for t in n.targets if isinstance(n, ast.Assign) else [n.target]:
                        found += [s.id for s in ast.walk(t) if isinstance(s, ast.Name)]
                elif isinstance(n, (ast.Import, ast.ImportFrom)):
                    found += [a.asname or a.name.split(".")[0] for a in n.names]
                elif isinstance(n, (ast.If, ast.Try)):
                    # try: import x / except ImportError: x = None, o bloques TYPE_CHECKING
                    found += [s.id for s in ast.walk(n) if isinstance(s, ast.Name) and isinstance(s.ctx, ast.Store)]
                    found += [a.asname or a.name.split(".")[0] for s in ast.walk(n) if isinstance(s, (ast.Import, ast.ImportFrom)) for a in s.names]
                    found += [s.name for s in ast.walk(n) if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
            found += [other.rsplit(".", 1)[1] for other in names if other.rsplit(".", 1)[0] == m.name and "." in other]
            self.map.symbols[m.name] = sorted(set(found))

    def fixtures(self) -> None:
        for m in self.modules:
            if PurePosixPath(m.path).name != "conftest.py":
                continue
            names = []
            for node in m.tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(_last(d) == "fixture" for d in node.decorator_list):
                    names.append(node.name)
            self.map.fixtures[m.path] = names

    def framework(self, requirements: str) -> None:
        mp = self.map
        imported = {mod.split(".")[0] for m in self.modules if not m.is_test for mod, _ in m.imports.values()}
        found = [f for f, libs in (("fastapi", {"fastapi"}), ("flask", {"flask"}), ("django", {"django", "rest_framework"})) if imported & libs]
        req = requirements.lower()
        for f in ("fastapi", "flask", "django"):
            if f not in found and re.search(rf"(^|\n)\s*{f}\b", req):
                found.append(f)
        mp.frameworks = found
        counts = {f: 0 for f in found}
        for e in mp.endpoints:
            module = next((m for m in self.modules if m.path == e.file), None)
            kind = "django" if module and ("django" in {x.split(".")[0] for x, _ in module.imports.values()} or "rest_framework" in {x.split(".")[0] for x, _ in module.imports.values()}) else None
            if kind and kind in counts:
                counts[kind] += 1
        for m in self.modules:
            for info in m.routers.values():
                f = "fastapi" if info[0] in ("FastAPI", "APIRouter") else "flask"
                if f in counts:
                    counts[f] += 1
        mp.framework = max(found, key=lambda f: (counts[f], -found.index(f))) if found else None


def _last_name(name: str) -> str:
    return name.rsplit(".", 1)[-1]


def _unique[T](items: list[T]) -> list[T]:
    seen = set()
    out = []
    for item in items:
        key = tuple(asdict(item).values())  # type: ignore[call-overload]
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _skip(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return any(part in SKIP_DIRS or part.startswith(".") for part in parts[:-1])


# Lo que usa una app que responde páginas (formularios) en lugar de JSON: (módulo, nombre importado)
HTML_IMPORTS = {("flask", "render_template"), ("flask", "flash"), ("django.shortcuts", "render")}


def _renders_html(m: _Module) -> bool:
    return any((mod, attr) in HTML_IMPORTS or mod.startswith("django.views.generic") for mod, attr in m.imports.values())


def build(root: Path, files: list[str] | None = None) -> ProjectMap:
    """Mapa del repo en `root`. `files` = rutas relativas (las del clon); None = recorrer la carpeta."""
    if files is None:
        files = [p.relative_to(root).as_posix() for p in root.rglob("*.py") if p.is_file()]
        # Los archivos que marcan dónde está el código (source_root): solo la raíz y el primer nivel
        files += [p.relative_to(root).as_posix() for m in SOURCE_MARKERS for pattern in (m, f"*/{m}") for p in root.glob(pattern) if p.is_file()]
    prefix = source_root(files, root)
    py = sorted(f for f in files if f.endswith(".py") and not _skip(f))
    warnings: list[str] = []
    if len(py) > MAX_FILES:
        warnings.append(f"El repo tiene {len(py)} archivos de Python: se leyeron los primeros {MAX_FILES}.")
        py = py[:MAX_FILES]
    modules: list[_Module] = []
    broken = 0
    for path in py:
        full = root / path
        try:
            if full.stat().st_size > MAX_FILE_BYTES:
                continue
            source = full.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        m = _read_module(path, source, prefix)
        if m is None:
            broken += 1
            continue
        modules.append(m)
    if broken:
        warnings.append(f"{broken} archivo(s) de Python no se pudieron leer (error de sintaxis).")

    requirements = ""
    for name in ("requirements.txt", "pyproject.toml", "setup.py", "Pipfile"):
        try:
            requirements += (root / prefix / name).read_text(encoding="utf-8", errors="replace")[:100_000] + "\n"
        except OSError:
            pass

    b = _Builder(modules)
    b.web_endpoints()
    b.django_endpoints()
    b.map.endpoints = b.map.endpoints[:MAX_ENDPOINTS]
    b.models_and_schemas()
    b.roles()
    b.places()
    b.fixtures()
    b.symbols()
    b.framework(requirements)
    mp = b.map
    mp.source_root = prefix
    mp.files = len(modules)
    mp.html = any(not m.is_test and _renders_html(m) for m in modules)
    mp.packages = sorted({m.name.split(".")[0] for m in modules if not m.is_test and m.name and m.name.split(".")[0] not in ("setup", "manage", "conftest", "noxfile")})
    if not mp.framework:
        warnings.append("No se reconoció FastAPI, Flask ni Django: las reglas solo se pueden verificar con patrones o con las pruebas del equipo.")
    elif not mp.endpoints:
        warnings.append(f"Se reconoció {mp.framework}, pero no se encontraron endpoints (¿rutas armadas dinámicamente?).")
    mp.warnings = warnings
    return mp
