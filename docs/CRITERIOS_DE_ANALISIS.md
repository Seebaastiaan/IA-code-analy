# Criterios de análisis · Seguridad, QA y Buenas Prácticas

Qué revisa IA voy en cada repositorio, con qué herramienta, cuánto resta cada hallazgo y qué **no** revisa.
Describe el producto completo (12 pasos). La columna "Sprint" indica cuándo entra cada parte.

## 1. Resumen

| Categoría | Herramientas | Qué mide | Peso por defecto | Sprint |
|---|---|---|---|---|
| **Seguridad** | Bandit, pip-audit | Patrones inseguros en el código y dependencias con vulnerabilidades conocidas | 50 % | **5** |
| **QA / Testing** | pytest, coverage | Si las pruebas del proyecto pasan y cuánto código ejecutan | 30 % | 6 |
| **Buenas Prácticas** | Ruff, Radon | Errores latentes, código innecesario o difícil de mantener, complejidad | 20 % | 6 |
| Reglas de negocio | patrones (7) · pytest (8) | Ver [PROPUESTA_REGLAS_NEGOCIO.md](PROPUESTA_REGLAS_NEGOCIO.md) | — (aún no cuenta) | **7** |

Alcance: **solo Python**. Se detectan otros lenguajes del repo, pero no se analizan.

Nunca se analizan las carpetas `.git`, `.venv`, `venv`, `env`, `node_modules`, `build`, `dist` ni
`site-packages`. Por defecto el proyecto también excluye `migrations/` y `tests/fixtures/`.

## 2. Cómo se calcula la calificación

```
Seguridad         = 100 − Σ penalización de hallazgos de seguridad abiertos
Buenas Prácticas  = 100 − Σ penalización de hallazgos de buenas prácticas abiertos
Testing           = cobertura total − 5 × pruebas que fallan
Global            = promedio ponderado con los pesos del proyecto
```

| Severidad | Seguridad | Buenas Prácticas |
|---|---|---|
| alta | −12 | −6 |
| media | −6 | −3 |
| baja | −2 | −1 |

- En proyectos de más de 1000 líneas de Python, la penalización se escala por cada 1000 líneas. Así, 60 avisos
  en 10 000 líneas pesan como 6 en 1000; si no, cualquier proyecto grande quedaría en 0.
- Todo se acota entre 0 y 100.
- Se recalcula al leer: resolver un hallazgo en el editor, ignorar una regla o cambiar los pesos se refleja sin
  volver a analizar.
- Umbrales por defecto: score mínimo **70**, cobertura mínima **60 %**.

## 3. Seguridad (Sprint 5)

### 3.1 Bandit: el código del proyecto

Lee el código, no lo ejecuta, y corre en el backend. **No revisa las pruebas** (`tests/`, `test_*.py`,
`*_test.py`), porque ahí los `assert` y los datos de prueba son normales.

| Detecta (ejemplos) | Regla |
|---|---|
| Contraseñas, tokens o claves escritas en el código | B105, B106, B107 |
| `eval()` / `exec()` | B307, B102 |
| `subprocess` con `shell=True`, `os.system` | B602, B605 |
| SQL armado con strings o f-strings (inyección SQL) | B608 |
| Hashes débiles (MD5, SHA1) y cifrados inseguros | B303, B324, B304 |
| `requests` con `verify=False` (sin validar el certificado) | B501 |
| `pickle` / `yaml.load` sin `SafeLoader` (deserialización insegura) | B301, B506 |
| Escuchar en todas las interfaces (`0.0.0.0`), archivos temporales inseguros | B104, B108 |
| `random` usado para algo de seguridad | B311 |
| `assert` en el código de la app (se borra con `python -O`) | B101 (**ignorada por defecto**) |

La severidad la da Bandit (HIGH → alta, MEDIUM → media, LOW → baja). Cada hallazgo indica además la confianza
de Bandit y el enlace a la documentación de la regla.

### 3.2 pip-audit: las dependencias

Corre **en el sandbox**: primero instala las dependencias del proyecto y luego las compara con las bases de
vulnerabilidades públicas (PyPI / OSV, identificadores PYSEC, GHSA y CVE).

| Hallazgo | Severidad | Detalle |
|---|---|---|
| Paquete con vulnerabilidad conocida | alta | Paquete, versión, identificadores y versión que la corrige; apunta a la línea del `requirements.txt` |
| `DEPS`: no se pudieron instalar las dependencias | alta | Sin instalarlas no se pueden revisar; incluye la salida de la instalación |

Cómo encuentra las dependencias (en la raíz del repo):

1. Si hay `requirements.txt`, se instala ese archivo.
2. Si no, y hay `pyproject.toml` o `setup.py`, se instala el proyecto (`-e .`).
3. Si no hay ninguno, no hay nada que instalar y pip-audit reporta 0 paquetes.

> ⚠️ "0 vulnerables" puede significar "no encontré dependencias". Los archivos `Pipfile`, `environment.yml`,
> `poetry.lock` solo, o dependencias en subcarpetas (`backend/requirements.txt`) no se detectan.

## 4. QA / Testing (Sprint 6)

Corre **en el sandbox**: ejecuta el código del proyecto.

| Herramienta | Qué hace |
|---|---|
| **pytest** | Corre las pruebas del proyecto (se detiene después de 50 fallos). IA voy instala pytest y coverage aunque el proyecto no los declare |
| **coverage** | Mide qué porcentaje de las líneas del código de la app ejecutan las pruebas (no cuenta las pruebas ni los archivos de herramientas) |

| Hallazgo | Regla | Severidad |
|---|---|---|
| Una prueba falla | `FAIL` | alta |
| Una prueba termina con error (por ejemplo, un import roto) | `ERROR` | alta |
| pytest no pudo correr (tiempo agotado, configuración rota) | `ERROR` | alta |
| Faltan dependencias, así que las pruebas no pueden importar el código | `DEPS` | alta |
| Archivo con cobertura bajo el mínimo | `COV` | media si está 15 puntos o más por debajo; si no, baja |

**Calificación**: `Testing = cobertura total − 5 × pruebas que fallan`. Ejemplos:

- 85 % de cobertura y 2 pruebas fallando → 75.
- **Sin pruebas** → ningún archivo medido → cobertura 0 → **Testing 0**.
- Si en el análisis no se elige coverage, la cobertura cuenta como 100 y solo se descuentan las pruebas que
  fallan.

> ⚠️ Sin sandbox (sin WSL ni Docker) las pruebas **no se ejecutan**: el producto final las simula para que la
> demo muestre datos. Para calificar un proyecto real, el análisis debe correr con sandbox.

**Qué no mide**: la calidad de las pruebas (una prueba sin `assert` cuenta igual), pruebas e2e, de carga o de
interfaz, ni pruebas en otros lenguajes. Las reglas de negocio ligadas a pruebas cubren parte de ese hueco.

## 5. Buenas Prácticas (Sprint 6)

### 5.1 Ruff: errores latentes y estilo

Si el proyecto tiene su propio `ruff.toml`, `.ruff.toml` o `[tool.ruff]` en `pyproject.toml`, se respeta.
Encima siempre se agregan los grupos `B`, `SIM` y `C4`.

| Grupo | Revisa (ejemplos) | Severidad |
|---|---|---|
| **E9 / F63 / F7 / F82** | Errores de sintaxis, `return` fuera de función, nombres no definidos (F821) | **alta** |
| **F** (Pyflakes) | Imports sin usar (F401), variables asignadas y nunca usadas (F841), `import *` (F403), f-strings sin variables (F541) | media |
| **B** (bugbear) | Argumentos mutables por defecto (B006), llamadas en valores por defecto (B008), `except` que se traga todo (B001), variable de ciclo no usada (B007) | media |
| **E4 / E7** | Imports fuera de lugar (E402), `== None` en vez de `is None` (E711), `except:` desnudo (E722), `lambda` asignada a variable (E731) | baja |
| **SIM** | Código simplificable: `if` anidados (SIM102), `if/else` que puede ser ternario (SIM108), `open` sin `with` (SIM115) | baja |
| **C4** | Comprensiones innecesarias: `list(x for x in …)` (C400), `dict([...])` (C406) | baja |

Desde el editor de la app, los hallazgos que Ruff marca como seguros se corrigen en un clic.

### 5.2 Radon: complejidad ciclomática

Mide por función cuántos caminos tiene el código (cada `if`, `for`, `while`, `and`/`or`, `except`):

| Grado | Complejidad | Lectura |
|---|---|---|
| A | 1–5 | Simple |
| B | 6–10 | Bien estructurada |
| C | 11–20 | Compleja: conviene dividir |
| D | 21–30 | Muy compleja |
| E | 31–40 | Difícil de probar |
| F | 41+ | Inmantenible |

> Hoy Radon **solo informa**: muestra la complejidad media y el ranking de funciones, pero **no resta puntos**.

**Qué no mide**: código duplicado, docstrings, anotaciones de tipo, nombres de variables o la arquitectura del
proyecto.

## 6. Qué puede ajustar cada proyecto

En **Configuración**, o en `.ia_voy.toml` en la raíz del repo, que se lee en cada análisis:

```toml
[pesos]
seguridad = 0.50
pruebas   = 0.30
practicas = 0.20

[umbrales]
score_minimo     = 70
cobertura_minima = 60

[reglas]
ignorar = ["B101"]                           # reglas de Bandit/Ruff que no aplican al proyecto

[rutas]
excluir = ["migrations/", "tests/fixtures/"]
```

Ignorar una regla o excluir una ruta debe justificarse (por ejemplo, un falso positivo). Queda visible en la
configuración del proyecto.

## 7. Cómo subir la calificación (para los equipos)

| Categoría | Acciones con más impacto |
|---|---|
| Seguridad | Sacar secretos del código (variables de entorno), actualizar los paquetes que pip-audit marca, consultas SQL parametrizadas, `subprocess` sin `shell=True` |
| Testing | Arreglar primero las pruebas que fallan (−5 cada una); después cubrir los archivos con 0 %; `requirements.txt` completo para que las pruebas importen el código |
| Buenas Prácticas | Corregir los errores de severidad alta (nombres no definidos); usar la corrección automática del editor para imports y variables sin usar; dividir las funciones de grado C o peor |
