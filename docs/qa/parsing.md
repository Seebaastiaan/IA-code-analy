# Esquema de parsing de reportes

Responsable: Evelyn Martínez (QA) · Sprint 2

Cada analizador entrega su resultado en un formato distinto. Este documento fija cómo se convierte cada
salida al contrato común `FindingInput` (`backend/app/analyses/models.py`), para que el pipeline, las
pruebas y el frontend hablen de lo mismo. Los ejemplos reales de cada formato están en
`backend/tests/fixtures/` (salidas de las herramientas sobre un proyecto de prueba).

## Contrato común

| Campo | Tipo | Descripción |
|---|---|---|
| `sev` | `alta` · `media` · `baja` | Severidad normalizada |
| `cat` | `seg` · `test` · `prac` | Categoría del score (seguridad, pruebas, buenas prácticas) |
| `tool` | `Bandit` · `pip-audit` · `pytest` · `coverage` · `Ruff` · `Radon` | Herramienta que lo detectó |
| `rule` | texto | Código de la regla (`B105`, `F401`, `COV`, `FAIL`, `requests 2.25.1`) |
| `file` | ruta relativa con `/` | Relativa a la raíz del repositorio |
| `line` | entero ≥ 1 | Línea señalada (1 si el hallazgo es del archivo completo) |
| `msg` | texto | Qué se encontró |
| `why` | texto | Por qué importa |
| `rec` | texto | Cómo corregirlo |
| `fix` | booleano | Hay corrección automática |

Reglas generales:

- Las rutas absolutas o con `./` se vuelven relativas a la raíz del clon y usan `/`.
- Se ignora todo lo que esté dentro de `.git`, `.venv`, `venv`, `node_modules`, `build`, `dist`.
- Si una herramienta no devuelve JSON válido, el análisis falla con un error claro (no se inventan hallazgos).

## Bandit → seguridad

Ejemplo: `fixtures/bandit.json` (`bandit -r . -f json`).

| Bandit | Contrato |
|---|---|
| `results[].test_id` | `rule` |
| `results[].filename` | `file` |
| `results[].line_number` | `line` |
| `results[].issue_text` | `msg` |
| `results[].issue_severity` (`HIGH`/`MEDIUM`/`LOW`) | `sev` (`alta`/`media`/`baja`) |
| `results[].more_info` | se cita en `why` |

`cat = "seg"`, `tool = "Bandit"`, `fix = false`. Los archivos de pruebas (`tests/`, `test_*.py`,
`*_test.py`) no se revisan con Bandit: un `assert` (B101) o una contraseña de ejemplo ahí no es un riesgo real.

## pip-audit → seguridad

Ejemplo: `fixtures/pip_audit.json` (`pip-audit -f json`).

- Una entrada por paquete con al menos una vulnerabilidad en `dependencies[].vulns`.
- `rule = "{paquete} {versión}"`, `sev = "alta"`, `file` = archivo de dependencias (`requirements.txt`,
  `pyproject.toml` o `setup.py`), `line` = línea donde aparece el paquete (1 si es una dependencia indirecta).
- `msg` lista los ids (`PYSEC-…`, `GHSA-…`) sin repetidos; `rec` sugiere la menor versión corregida.

## pytest → pruebas

Ejemplo: `fixtures/pytest_junit.xml` (`pytest --junitxml=… -o junit_family=xunit1`).

- Cada `<testcase>` con `<failure>` o `<error>` es un hallazgo `rule = "FAIL"` o `"ERROR"`, `sev = "alta"`.
- `file` sale del atributo `file` (xunit1); `line` viene desde 0, se suma 1.
- `<skipped>` no genera hallazgo, solo cuenta en el resumen.
- Si pytest no pudo correr (código distinto de 0, 1 o 5), un solo hallazgo `ERROR` con la salida.

## coverage → pruebas

Ejemplo: `fixtures/coverage.json` (`coverage json`).

- Por archivo: `files[ruta].summary.covered_lines / num_statements`.
- Un hallazgo `rule = "COV"` por archivo bajo el mínimo del proyecto (60 % por defecto), `line = 1`.
  `sev = "media"` si está más de 15 puntos por debajo; si no, `baja`.
- Los archivos de pruebas no cuentan para la cobertura.

## Ruff → buenas prácticas

Ejemplo: `fixtures/ruff.json` (`ruff check . --output-format json`).

| Ruff | Contrato |
|---|---|
| `code` | `rule` |
| `filename` | `file` |
| `location.row` | `line` |
| `message` | `msg` |
| `fix.applicability == "safe"` | `fix = true` |

Severidad por prefijo: `E9`, `F63`, `F7`, `F82` (sintaxis, nombres no definidos) → `alta`; `F*` y `B*` → `media`;
el resto → `baja`.

## Radon → buenas prácticas

Ejemplo: `fixtures/radon_cc.json` (`radon cc -j`).

Radon no genera hallazgos sino la tabla de complejidad del reporte: una fila por función con
`fn` (`Clase.metodo` o `funcion`), `file`, `cc` (complejidad) y `grade`:

| CC | 1–5 | 6–10 | 11–20 | 21–30 | 31–40 | > 40 |
|---|---|---|---|---|---|---|
| Grado | A | B | C | D | E | F |

Si Radon no puede leer un archivo devuelve `{"error": …}` en lugar de la lista: ese archivo se omite.
