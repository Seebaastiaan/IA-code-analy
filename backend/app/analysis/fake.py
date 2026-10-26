"""
Métricas SIMULADAS mientras no corren los analizadores reales (Bandit, pytest, Ruff…).
Todo se deriva de una semilla guardada con el reporte, así que un mismo reporte siempre se ve igual.
"""

import random

# Los 10 pasos del análisis del Sprint 6 (el índice del asistente llega en el Sprint 7) (mismo orden que frontend/src/features/analysis/constants/jobSteps.ts)
JOB_STEPS: list[tuple[str, str]] = [
    ("Clonando repositorio", "git clone --depth 1 --branch {branch} {url}"),
    ("Creando entorno aislado", "uv venv .venv  (sandbox)"),
    ("Instalando dependencias", "uv pip install -r requirements.txt"),
    ("Bandit", "bandit -r . -f json"),
    ("pip-audit", "pip-audit --path .venv/…/site-packages -f json"),
    ("pytest", "coverage run -m pytest -q --maxfail=50"),
    ("coverage", "coverage json"),
    ("Ruff", "ruff check . --output-format json"),
    ("Radon", "radon cc . -j && radon mi . -j"),
    ("Calculando score", "agregación ponderada (.ia_voy.toml)"),
]

DEFAULT_WEIGHTS = {"seg": 50, "test": 30, "prac": 20}
DEFAULT_THRESHOLDS = {"score": 70, "cov": 60}
SEV_ORDER = {"alta": 0, "media": 1, "baja": 2}

FINDINGS: list[dict] = [
    {"id": 1, "sev": "alta", "cat": "seg", "tool": "Bandit", "rule": "B105", "file": "auth.py", "line": 15, "fix": False,
     "msg": "Clave secreta escrita directamente en el código",
     "why": "Cualquier persona con acceso al repositorio puede firmar tokens válidos y suplantar usuarios.",
     "rec": "Leer la clave desde una variable de entorno y rotar la clave expuesta."},
    {"id": 2, "sev": "alta", "cat": "seg", "tool": "Bandit", "rule": "B608", "file": "api.py", "line": 17, "fix": False,
     "msg": "Posible inyección SQL por concatenación de cadenas",
     "why": "Un valor que llega desde la URL se inserta sin escapar en la consulta.",
     "rec": "Usar consultas parametrizadas con marcadores \"?\"."},
    {"id": 3, "sev": "alta", "cat": "seg", "tool": "pip-audit", "rule": "requests 2.25.1", "file": "requirements.txt", "line": 4, "fix": False,
     "msg": "Dependencia con vulnerabilidad conocida",
     "why": "La versión instalada tiene avisos de seguridad publicados.",
     "rec": "Actualizar a la versión más reciente sin avisos y volver a correr las pruebas."},
    {"id": 4, "sev": "media", "cat": "seg", "tool": "Bandit", "rule": "B324", "file": "utils.py", "line": 9, "fix": False,
     "msg": "Hash débil (MD5) usado para validar contraseñas",
     "why": "MD5 tiene colisiones conocidas y es demasiado rápido para proteger contraseñas.",
     "rec": "Usar SHA-256 para huellas, o bcrypt/argon2 si es una contraseña."},
    {"id": 5, "sev": "media", "cat": "seg", "tool": "Bandit", "rule": "B311", "file": "tokens.py", "line": 9, "fix": False,
     "msg": "random no es criptográficamente seguro",
     "why": "Los tokens generados con random pueden predecirse.",
     "rec": "Usar el módulo secrets (secrets.choice o secrets.token_urlsafe)."},
    {"id": 6, "sev": "media", "cat": "test", "tool": "coverage", "rule": "COV", "file": "core/servicios.py", "line": 1, "fix": False,
     "msg": "Cobertura de 31 % (umbral: 60 %)",
     "why": "La lógica principal casi no tiene pruebas.",
     "rec": "Agregar pruebas para los casos principales y los de error."},
    {"id": 7, "sev": "media", "cat": "test", "tool": "pytest", "rule": "FAIL", "file": "tests/test_api.py", "line": 13, "fix": False,
     "msg": "test_crear_registro_invalido falló (AssertionError)",
     "why": "Una prueba fallida indica que el comportamiento esperado cambió o hay un error.",
     "rec": "Revisar el código de estado esperado (400 vs 422)."},
    {"id": 8, "sev": "media", "cat": "prac", "tool": "Radon", "rule": "CC · D", "file": "core/procesador.py", "line": 20, "fix": False,
     "msg": "Complejidad ciclomática 24 en procesar_lote()",
     "why": "Funciones muy complejas son difíciles de probar y mantener.",
     "rec": "Dividir la función en pasos más pequeños (validar, agrupar, procesar)."},
    {"id": 9, "sev": "baja", "cat": "prac", "tool": "Ruff", "rule": "F401", "file": "api.py", "line": 3, "fix": False,
     "msg": "Import sin usar: os",
     "why": "Código muerto que confunde a quien lee el archivo.",
     "rec": "Eliminar el import."},
    {"id": 10, "sev": "baja", "cat": "prac", "tool": "Ruff", "rule": "E501", "file": "core/procesador.py", "line": 38, "fix": False,
     "msg": "Línea demasiado larga (128 > 100)",
     "why": "Dificulta la lectura y las revisiones de código.",
     "rec": "Partir la expresión en varias líneas."},
    {"id": 11, "sev": "baja", "cat": "prac", "tool": "Ruff", "rule": "B006", "file": "utils.py", "line": 17, "fix": False,
     "msg": "Argumento por defecto mutable",
     "why": "La lista por defecto se comparte entre llamadas y acumula valores.",
     "rec": "Usar None como valor por defecto y crear la lista dentro."},
    {"id": 12, "sev": "baja", "cat": "test", "tool": "pytest", "rule": "SKIP", "file": "tests/test_auth.py", "line": 6, "fix": False,
     "msg": "3 pruebas omitidas con @skip",
     "why": "Pruebas omitidas pueden ocultar regresiones.",
     "rec": "Reactivarlas o documentar por qué se omiten."},
]

COVERAGE_FILES = ["auth.py", "utils.py", "api.py", "tokens.py", "core/procesador.py", "core/servicios.py"]

COMPLEXITY_FNS = [
    ("procesar_lote", "core/procesador.py"),
    ("validar_entrada", "core/procesador.py"),
    ("calcular_totales", "core/servicios.py"),
    ("crear_token", "auth.py"),
    ("listar_registros", "api.py"),
    ("huella", "utils.py"),
]


def clamp(v: float) -> int:
    return max(0, min(100, round(v)))


def global_score(cat: dict, weights: dict = DEFAULT_WEIGHTS) -> float:
    total = sum(weights.values()) or 1
    return round(sum(weights[k] * cat[k] for k in weights) / total, 1)


def scores(cat: dict) -> dict:
    return {"seg": cat["seg"], "test": cat["test"], "prac": cat["prac"], "global": global_score(cat)}


def next_categories(prev: dict | None, rng: random.Random) -> dict:
    """Primer análisis: valores entre 55 y 92. Siguientes: el anterior con una variación de ±6."""
    if prev is None:
        return {k: rng.randint(55, 92) for k in ("seg", "test", "prac")}
    return {k: clamp(prev[k] + rng.randint(-6, 6)) for k in ("seg", "test", "prac")}


def _grade(cc: int) -> str:
    return "A" if cc <= 5 else "B" if cc <= 10 else "C" if cc <= 20 else "D" if cc <= 30 else "E" if cc <= 40 else "F"


def details(seed: int, cat: dict) -> dict:
    """Hallazgos, cobertura, complejidad y resumen de un reporte. Peor categoría ⇒ más hallazgos en ella."""
    rng = random.Random(seed)
    findings = []
    for f in FINDINGS:
        # Probabilidad de que aparezca: alta si la categoría tiene score bajo
        if rng.random() < (100 - cat[f["cat"]]) / 45:
            findings.append({**f, "status": "open"})
    findings.sort(key=lambda f: SEV_ORDER[f["sev"]])

    base_cov = cat["test"]
    coverage = sorted(({"file": name, "percent": clamp(base_cov + rng.randint(-35, 15))} for name in COVERAGE_FILES), key=lambda c: -c["percent"])

    complexity = []
    for fn, file in COMPLEXITY_FNS:
        cc = max(1, round((100 - cat["prac"]) / 3 + rng.randint(-8, 10)))
        complexity.append({"fn": fn, "file": file, "cc": cc, "grade": _grade(cc)})
    complexity.sort(key=lambda c: -c["cc"])

    summary = {
        "coverage_total": round(sum(c["percent"] for c in coverage) / len(coverage)),
        "tests_failed": sum(1 for f in findings if f["rule"] == "FAIL"),
        "avg_complexity": round(sum(c["cc"] for c in complexity) / len(complexity), 1),
    }
    return {"findings": findings, "coverage": coverage, "complexity": complexity, "summary": summary}


def step_summary(step: int, seed: int, cat: dict) -> str | None:
    """Línea de resultado que muestra la terminal al terminar cada analizador."""
    d = details(seed, cat)
    by = lambda tool: [f for f in d["findings"] if f["tool"] == tool]
    bandit = by("Bandit")
    lines = {
        3: f"  {sum(f['sev'] == 'alta' for f in bandit)} alta · {sum(f['sev'] == 'media' for f in bandit)} media · {sum(f['sev'] == 'baja' for f in bandit)} baja",
        4: f"  {len(by('pip-audit'))} paquete(s) vulnerable(s)",
        5: f"  {rng_passed(seed)} passed, {d['summary']['tests_failed']} failed, {len([f for f in d['findings'] if f['rule'] == 'SKIP']) * 3} skipped",
        6: f"  cobertura total: {d['summary']['coverage_total']} %",
        7: f"  {len(by('Ruff'))} problema(s)",
        8: f"  complejidad media: {d['summary']['avg_complexity']}",
        9: f"  score global: {global_score(cat)}",
    }
    return lines.get(step)


def rng_passed(seed: int) -> int:
    return random.Random(seed + 1).randint(40, 180)
