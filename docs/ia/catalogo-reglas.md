# Catálogo de reglas y severidades

Responsable: Marco Espino (IA & Analizadores) · Sprint 6

Qué detecta cada analizador, con qué severidad entra al reporte y cuánto pesa en el score. Lo implementan
`backend/app/analyses/analyzers.py` (Ruff, Bandit, Radon), `backend/app/analysis/pipeline.py` (pip-audit,
pytest, coverage) y `backend/app/analyses/scoring.py` (penalizaciones).

## Penalización por severidad

| Categoría | Alta | Media | Baja |
|---|---|---|---|
| Seguridad (`seg`) | 12 | 6 | 2 |
| Buenas prácticas (`prac`) | 6 | 3 | 1 |

Pruebas (`test`) no usa penalización por hallazgo: `test = cobertura total − 5 × pruebas que fallan`.
En proyectos de más de 1000 líneas de Python la penalización se multiplica por `1000 / líneas`.

## Seguridad

### Bandit (solo código, no pruebas)

| Severidad de Bandit | Severidad en IA voy |
|---|---|
| `HIGH` | alta |
| `MEDIUM` | media |
| `LOW` | baja |

Reglas que aparecen en el repo de demostración (`backend/seed_data/demo_repo`):

| Regla | Qué detecta | Severidad |
|---|---|---|
| B105 | Contraseña o clave escrita en el código | baja |
| B201 | Flask con `debug=True` | alta |
| B311 | `random` para tokens o valores secretos | baja |
| B324 | Hash débil (MD5/SHA1) | alta |
| B404 | Importar `subprocess` | baja |
| B602 | `subprocess` con `shell=True` | alta |
| B608 | SQL armado por concatenación de cadenas | media |

`B101` (uso de `assert`) se ignora por defecto: en pytest es lo normal.

### pip-audit

| Hallazgo | Severidad | Archivo y línea |
|---|---|---|
| Un paquete instalado con al menos un aviso de seguridad (`PYSEC-…`, `GHSA-…`) | alta | Línea del paquete en `requirements.txt` / `pyproject.toml`; 1 si es una dependencia indirecta |

La recomendación indica la menor versión que corrige todos los avisos, o que no hay versión corregida.

## Pruebas

| Herramienta | Regla | Cuándo | Severidad |
|---|---|---|---|
| pytest | `FAIL` | Una prueba falló (assert) | alta |
| pytest | `ERROR` | Una prueba terminó con error, o pytest no pudo correr | alta |
| pytest | `DEPS` | No se pudieron instalar las dependencias del proyecto | alta |
| coverage | `COV` | Archivo con cobertura bajo el mínimo (60 % por defecto) | media si está más de 15 puntos por debajo; si no, baja |

Los archivos de pruebas y de herramientas (`setup.py`, `conftest.py`, `manage.py`, `docs/`…) no cuentan para la
cobertura.

## Buenas prácticas

### Ruff

Reglas fijas `E4,E7,E9,F,B,SIM,C4`: las que eran por defecto (`E4`, `E7`, `E9`, `F`) más `B` (bugbear), `SIM`
(simplificaciones) y `C4` (comprensiones). Se pasan con `--select` porque desde Ruff 0.17 el conjunto por defecto
trae ~400 reglas (orden de imports, `UP*`, copyright…) que llenaban el reporte de ruido. Si el repositorio trae su
propia configuración de Ruff, se usa la suya más `B,SIM,C4`.

| Prefijo | Ejemplos | Severidad |
|---|---|---|
| `E9`, `F63`, `F7`, `F82` | Error de sintaxis, nombre no definido | alta |
| `F*` | `F401` import sin usar, `F841` variable sin usar | media |
| `B*` | `B006` argumento mutable por defecto, `B008` llamada en un default | media |
| Resto (`E`, `SIM`, `C4`, `I`) | `E501` línea larga, `SIM108` usar ternario | baja |

## Recomendaciones y correcciones

Cada hallazgo de Bandit y Ruff trae una recomendación concreta en español: qué cambiar y con qué código
([`backend/app/analyses/remedies.py`](../../backend/app/analyses/remedies.py)). Ya no dice "revisa la
documentación" ni manda a un enlace. Las reglas de Ruff que no están en el catálogo usan el ejemplo "Use instead"
de la documentación de la propia regla.

Todos los hallazgos que se pueden arreglar con un cambio en el código se marcan **Fix** (`fix_kind`):

| `fix_kind` | Qué hallazgos | Quién propone el cambio |
|---|---|---|
| `auto` | Ruff con corrección `safe` o `unsafe`; pip-audit en un `requirements*.txt` (sube la versión) | La herramienta, determinista |
| `ia` | Bandit, Ruff sin corrección, pruebas que fallan de verdad (no simuladas), pip-audit en `pyproject.toml` | El LLM (`POST /api/fix`), con ediciones solo dentro de la función del hallazgo; si el resultado no compila se rechaza |
| — | `COV` (falta escribir pruebas), `DEPS` (el entorno no se instala), pruebas simuladas | No se corrigen con un parche |

En ambos casos el editor muestra el diff y nada se guarda hasta que la persona acepta. Las correcciones con IA
necesitan `GEMINI_API_KEY`; las `auto` funcionan sin ella.

### Radon

Radon no genera hallazgos: alimenta la tabla de complejidad del reporte y el promedio del resumen.

| Complejidad ciclomática | 1–5 | 6–10 | 11–20 | 21–30 | 31–40 | > 40 |
|---|---|---|---|---|---|---|
| Grado | A | B | C | D | E | F |

## Reglas ignoradas y rutas excluidas

Por defecto se ignora `B101` y se excluyen `migrations/` y `tests/fixtures/`. Cada proyecto puede cambiarlo
(pantalla Configuración y `.ia_voy.toml`).
