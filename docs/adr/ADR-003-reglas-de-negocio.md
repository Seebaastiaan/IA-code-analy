# ADR-003 · Las reglas de negocio se declaran en el repo analizado y se verifican de forma determinista

- Estado: aceptada · en implementación (Sprint 7: archivo, validación y nivel patrón)
- Fecha: 25 de octubre de 2026 (Sprint 5); actualizada el 7 de noviembre de 2026 (Sprint 7)
- Responsable: por definir

## Contexto

IA voy califica Seguridad (Bandit, pip-audit), Testing (pytest, coverage) y Buenas Prácticas (Ruff, Radon).
Ninguna de esas herramientas sabe qué debe hacer **cada** proyecto: un sistema de pagos y uno escolar pueden
pasar las tres categorías y aun así romper la regla más importante de su negocio.

Se pidió que el sistema tome en cuenta las reglas de negocio de cada proyecto, y que **no** sea solo la IA la
que las lea e interprete: deben ser parte del proyecto que se entrega. Leerlas solo con un LLM daría
resultados distintos en cada análisis, sin evidencia verificable, y contradice el motor determinista
([ADR-001](ADR-001-motor-determinista.md)).

## Decisión

Cada proyecto **declara** sus reglas en su propio repositorio (`reglas_negocio.toml`) y las **liga** a algo verificable. IA voy las lee
al clonar, las verifica con el mismo sandbox de pruebas ([ADR-002](ADR-002-sandbox.md)) y reporta el resultado
con evidencia. La IA solo explica.

### 1. Declaración: archivo `reglas_negocio.toml` en la raíz del repo analizado

Un archivo propio, no una sección de `.ia_voy.toml`: ahí `[reglas]` ya significa "reglas de Bandit/Ruff
ignoradas" (TOML no admite `[reglas]` y `[[reglas]]` juntos) y la pantalla de Configuración reescribe ese
archivo completo al guardar. El archivo se versiona con git como el resto del código; también se puede cargar
desde Configuración → Reglas de negocio, pero si el repo lo tiene, gana el del repo. Formato, campos y
nomenclatura completos en [PROPUESTA_REGLAS_NEGOCIO.md](../PROPUESTA_REGLAS_NEGOCIO.md).

```toml
[proyecto]
nombre = "Tienda escolar"

[[regla]]
id          = "RN-001"
titulo      = "Montos con Decimal"
descripcion = "Todo monto de dinero se calcula con Decimal; nunca con float."
severidad   = "alta"                       # alta | media | baja
rutas       = ["app/pagos/", "app/facturas/"]
prohibido   = 'float\(.*(monto|precio|total)'

[[regla]]
id          = "RN-002"
titulo      = "Un pedido cancelado no vuelve a pagado"
descripcion = "Una vez cancelado, el estado de un pedido no puede cambiar a 'pagado'."
severidad   = "alta"
# Sin patrón: la cubren las pruebas marcadas con @pytest.mark.regla("RN-002")

[[regla]]
id          = "RN-003"
titulo      = "Rutas de administración protegidas"
descripcion = "Toda ruta bajo /admin exige el decorador @requiere_admin."
severidad   = "media"
rutas       = ["app/admin/"]
obligatorio = '@requiere_admin'
```

### 2. Verificación: tres niveles, solo los dos primeros cuentan en el score

| Nivel | Cómo se liga la regla | Quién la verifica | Resultado |
|---|---|---|---|
| **Pruebas** (principal) | Tests del proyecto marcados `@pytest.mark.regla("RN-02")` | pytest en el sandbox (`--junitxml`, ya existente desde el Sprint 6) | Pasan, fallan o no hay pruebas para la regla |
| **Patrón** | `prohibido` / `obligatorio` (expresión regular) sobre los archivos de `rutas` | Backend, como Bandit y Ruff: solo lee el código | `archivo:línea` donde se rompe |
| **IA** (apoyo) | Ninguno: la regla solo tiene `descripcion` | El asistente (RAG sobre el índice del repo) | "Sugerido por IA", con evidencia; **no** entra al score hasta que una persona lo confirme |

Cada regla termina en uno de tres estados:

- **Cumple**: sus pruebas pasan y no rompe su patrón.
- **No cumple**: falla una prueba o aparece el patrón → hallazgo con la severidad de la regla.
- **Sin verificar**: no tiene pruebas ni patrón → hallazgo de severidad baja ("regla declarada sin prueba").

### 3. Lugar en el análisis

- Un paso más, **"Verificando reglas de negocio"**, entre Radon y "Calculando score": el análisis pasa de 11 a
  **12 pasos**. Si el repo no declara reglas, el paso termina con "sin reglas declaradas" y no afecta el score.
- Una categoría nueva en el score, **Reglas de negocio** (`neg`), con su peso en `.ia_voy.toml` (`[pesos] negocio`):
  `neg = 100 − Σ penalización de las reglas que no cumplen o están sin verificar` (misma escala que Seguridad).
- Una vista **Reglas** con la matriz regla → estado → evidencia (test o `archivo:línea`).
- El asistente recibe las reglas del proyecto en su contexto: al explicar un hallazgo puede decir qué regla
  rompe y sugerir la prueba que falta.

### 4. Reglas de validación del archivo

- `id` único con formato `RN-###` (`RN-001`); máximo 200 reglas (como `MAX_RULES` de `config_file.py`).
- Una expresión regular inválida es un error de configuración, no un hallazgo: se reporta al guardar el archivo.
- `rutas` vacío = todo el repo, menos las rutas `excluidas` del proyecto.

### 5. Implementación por sprints

- **Sprint 7**: `reglas_negocio.toml` con su validación, nivel patrón y paso "Verificando reglas de negocio"
  (`backend/app/analyses/reglas.py`). Los resultados se guardan en tablas propias (`business_rule_checks`,
  `business_rule_results`) y no como hallazgos: la tabla `findings` solo admite `cat IN ('seg','test','prac')`
  (un `CHECK` que SQLite no deja cambiar sin reconstruir la tabla) y las categorías están fijas en el backend y
  el frontend. Todavía no entran al score. API: `GET /api/report/{id}/reglas`.
- **Sprint 8**: nivel pruebas (nombre `test_rn###_…` y plugin `-p ia_voy_reglas`), pestaña en Configuración y
  vista Reglas.
- **Después**: categoría `neg` en el score (migración de `reports` y de las categorías fijas) y nivel IA.

## Alternativas descartadas

- **Que la IA deduzca las reglas del README o del código**: no es reproducible, no deja evidencia y el equipo no
  tiene forma de corregirla. Se conserva solo como nivel de apoyo.
- **Programar en IA voy las reglas de cada proyecto**: no escala; IA voy analiza cualquier repositorio.
- **Un formato propio de reglas (DSL) o un motor de reglas**: más poder, pero obliga a cada equipo a aprender
  otro lenguaje. Las pruebas en pytest ya son el lenguaje del proyecto, y los patrones cubren lo que se ve en el
  código.

## Consecuencias

- Las reglas de negocio quedan **dentro del entregable** de cada equipo, versionadas y probadas; la nota sale
  de evidencia (pruebas y líneas de código), no de una opinión.
- Una regla sin prueba se vuelve visible: Testing mide cuánto código prueban los tests y Reglas de negocio mide
  si lo importante del negocio está probado.
- Depende del sandbox (pytest): con `SANDBOX=off` solo se verifican los patrones y las reglas ligadas a pruebas
  quedan "sin verificar (sandbox apagado)".
- Plan sugerido: primero los niveles de pruebas y patrón (deterministas, reutilizan el estilo de `config_file.py`
  y la fase `tests` del sandbox); después la carga desde Configuración y el nivel de IA, que reutiliza el
  asistente.
