"""
Matriz de permisos de las reglas de tipo `permisos` (docs/PROPUESTA_REGLAS_VERIFICABLES.md §6.3, fase 5).

Los documentos casi nunca dan la matriz completa. Con el mapa del proyecto (app.analyses.mapa) se arma una tabla:
filas = acciones sensibles (endpoints con autenticación que escriben, o que solo algunos roles pueden usar),
columnas = roles detectados. El equipo marca cada celda como «permitido» o «prohibido»; lo que no marca queda fuera.

La prueba sale de la tabla **sin IA**: una prueba parametrizada (rol × acción) que llama a la acción como ese rol.
- «permitido»: la respuesta no es un rechazo por permisos (ni 401 ni 403).
- «prohibido»: la respuesta es 403 (o 401).
Los ids de las rutas apuntan a un registro que no existe (999999): el permiso se revisa antes de buscar el registro
(decorador, dependencia o permiso del framework), así que un rol permitido recibe 404 y uno prohibido 403. Si un rol
prohibido recibe 404, el código buscó el registro antes de revisar el permiso y no se puede saber: la prueba queda
**rota** (no se culpa al código).

Lo que hace el código hoy (los roles que el mapa leyó) se muestra como sugerencia, pero no se copia solo: el oráculo es
la regla, no el código (PROPUESTA §12.2, pynguin).
"""

import re
from dataclasses import asdict, dataclass, field

from app.analyses import mapa, reglas

MAX_ACTIONS = 40
MAX_ROLES = 12
CELL = ("permitido", "prohibido")
# Rutas que no se revisan por rol (alta de usuarios, sesión, documentación)
PUBLIC = re.compile(r"/(login|logout|token|registro|register|signup|docs|openapi|health|salud)\b", re.IGNORECASE)
WRITES = ("POST", "PUT", "PATCH", "DELETE")
MISSING_ID = "999999"


class MatrixError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class Action:
    # "PATCH /servicios/{servicio_id}"
    id: str
    method: str
    path: str
    function: str
    # Roles que el código deja pasar hoy, según el mapa (vacío = no se sabe)
    suggested: list[str] = field(default_factory=list)
    # rol → permitido | prohibido (lo que no está, queda fuera de la matriz)
    cells: dict[str, str] = field(default_factory=dict)


@dataclass
class Matrix:
    roles: list[str]
    actions: list[Action]

    def to_dict(self) -> dict:
        return asdict(self)

    def cases(self) -> list[tuple[str, str, bool]]:
        return [(a.id, rol, a.cells[rol] == "permitido") for a in self.actions for rol in self.roles if a.cells.get(rol) in CELL]


PERMISSIONS_WORDS = re.compile(r"\bpermis|\broles?\b|\bautoriz|\bacceso\b|\bpermission|\baccess\b", re.IGNORECASE)


def looks_like_permissions(rule: reglas.BusinessRule) -> bool:
    """La regla habla de permisos o roles: se le ofrece la matriz (también si su prueba generada es de tipo permisos)."""
    return bool(PERMISSIONS_WORDS.search(" ".join([rule.title, rule.description, rule.criterion or ""])))


def propose(project_map: mapa.ProjectMap) -> Matrix:
    """Acciones sensibles del mapa, con las celdas vacías y lo que hace el código como sugerencia."""
    roles = list(dict.fromkeys(project_map.roles))[:MAX_ROLES]
    actions: list[Action] = []
    seen: set[str] = set()
    for e in project_map.endpoints:
        key = f"{e.method} {e.path}"
        if key in seen or PUBLIC.search(e.path):
            continue
        restricted = bool(e.roles) and len(set(e.roles) & set(roles)) < len(roles)
        if not e.auth or not (e.method in WRITES or restricted):
            continue
        seen.add(key)
        actions.append(Action(key, e.method, e.path, e.function, [r for r in roles if r in e.roles]))
    return Matrix(roles, actions[:MAX_ACTIONS])


def from_dict(data: dict | None, project_map: mapa.ProjectMap) -> Matrix:
    """
    La matriz guardada sobre la propuesta del mapa de hoy: se conservan las celdas marcadas de las acciones y roles
    que siguen existiendo (si el código cambió, las nuevas salen vacías y las que ya no existen se van).
    """
    base = propose(project_map)
    if not data:
        return base
    cells = {str(a.get("id")): a.get("cells") or {} for a in data.get("actions") or [] if isinstance(a, dict)}
    for a in base.actions:
        saved = cells.get(a.id) or {}
        a.cells = {r: v for r, v in saved.items() if r in base.roles and v in CELL}
    return base


def update(project_map: mapa.ProjectMap, cells: dict[str, dict[str, str | None]]) -> Matrix:
    """Matriz con las celdas que mandó el equipo (acción → rol → permitido | prohibido | None)."""
    m = propose(project_map)
    known = {a.id for a in m.actions}
    unknown = [k for k in cells if k not in known]
    if unknown:
        raise MatrixError("unknown_action", f"{', '.join(unknown[:5])} no es una acción del mapa del proyecto")
    for a in m.actions:
        for rol, value in (cells.get(a.id) or {}).items():
            if rol not in m.roles:
                raise MatrixError("unknown_role", f"`{rol}` no es un rol del proyecto ({', '.join(m.roles)})")
            if value is not None and value not in CELL:
                raise MatrixError("bad_cell", f"{a.id} · {rol}: usa «permitido», «prohibido» o vacío")
            if value:
                a.cells[rol] = value
    return m


def _call(framework: str | None) -> str:
    """Cómo manda un cuerpo JSON vacío el cliente del framework (Django: data + format; los demás: json=)."""
    if framework == "django":
        return 'llamar(ruta, {}, format="json")'
    return "llamar(ruta, json={})"


def test_code(rule: reglas.BusinessRule, m: Matrix, framework: str | None) -> str:
    """La prueba de la matriz (determinista: misma matriz, mismo código)."""
    cases = m.cases()
    if not cases:
        raise MatrixError("empty_matrix", "Marca al menos una celda como «permitido» o «prohibido»")
    n = rule.id.replace("-", "").lower()
    lines = [
        '"""',
        f"{rule.id} · {rule.title}",
        "Matriz rol × acción marcada por el equipo en IA voy (sin IA). «permitido»: no la rechaza por permisos (ni 401",
        "ni 403); «prohibido»: responde 403 (o 401). Las rutas apuntan a un registro que no existe: el permiso se revisa",
        "antes de buscarlo. Se vuelve a generar al cambiar la matriz.",
        '"""',
        "",
        "import re",
        "",
        "import pytest",
        "",
        f'SIN_REGISTRO = "{MISSING_ID}"',
        "CASOS = [",
        *(f"    ({accion!r}, {rol!r}, {permitido!r})," for accion, rol, permitido in cases),
        "]",
        "",
        "",
        f'@pytest.mark.regla("{rule.id}")',
        '@pytest.mark.parametrize(("accion", "rol", "permitido"), CASOS, ids=[f"{a}-{r}" for a, r, _ in CASOS])',
        f"def test_{n}_matriz_de_permisos(como, preparar, accion, rol, permitido):",
        '    metodo, plantilla = accion.split(" ", 1)',
        r'    ruta = re.sub(r"\{[^}]*\}|<[^>]*>", SIN_REGISTRO, plantilla)',
        "    llamar = getattr(como(rol), metodo.lower())",
        f'    r = {_call(framework)} if metodo in ("POST", "PUT", "PATCH") else llamar(ruta)',
        "    if permitido:",
        '        assert r.status_code not in (401, 403), f"{rol} debería poder {accion} y fue rechazado ({r.status_code})"',
        "        return",
        "    preparar(",
        "        r.status_code != 404 or ruta == plantilla,",
        '        f"{accion} respondió 404 a {rol}: el código busca el registro antes de revisar el permiso; crea el registro en la prueba",',
        "    )",
        '    assert r.status_code in (401, 403), f"{rol} no debería poder {accion} (respondió {r.status_code})"',
        "",
    ]
    return "\n".join(lines)
