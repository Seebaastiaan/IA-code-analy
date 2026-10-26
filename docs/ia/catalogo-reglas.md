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

Reglas por defecto de Ruff (`E4`, `E7`, `E9`, `F`) más `B` (bugbear), `SIM` (simplificaciones) y `C4`
(comprensiones). Si el repositorio trae su propia configuración de Ruff, se usa la suya.

| Prefijo | Ejemplos | Severidad |
|---|---|---|
| `E9`, `F63`, `F7`, `F82` | Error de sintaxis, nombre no definido | alta |
| `F*` | `F401` import sin usar, `F841` variable sin usar | media |
| `B*` | `B006` argumento mutable por defecto, `B008` llamada en un default | media |
| Resto (`E`, `SIM`, `C4`, `I`) | `E501` línea larga, `SIM108` usar ternario | baja |

Las reglas con corrección "safe" de Ruff se marcan con **Fix**: el editor (Sprint 7) las aplica.

### Radon

Radon no genera hallazgos: alimenta la tabla de complejidad del reporte y el promedio del resumen.

| Complejidad ciclomática | 1–5 | 6–10 | 11–20 | 21–30 | 31–40 | > 40 |
|---|---|---|---|---|---|---|
| Grado | A | B | C | D | E | F |

## Reglas ignoradas y rutas excluidas

Por defecto se ignora `B101` y se excluyen `migrations/` y `tests/fixtures/`. Cada proyecto puede cambiarlo
(pantalla Configuración y `.ia_voy.toml`).
