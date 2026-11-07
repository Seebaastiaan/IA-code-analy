# Propuesta · Reglas de negocio por proyecto

> Estado: en implementación (Sprint 7: archivo, validación y patrones; ver ADR-003 §5). Propuesta del 25 de octubre de 2026. Decisión técnica resumida en
> [ADR-003](adr/ADR-003-reglas-de-negocio.md).

## 1. Qué se busca

IA voy hoy califica **Seguridad**, **Testing** y **Buenas Prácticas** (ver
[CRITERIOS_DE_ANALISIS.md](CRITERIOS_DE_ANALISIS.md)). Esas herramientas no saben qué debe hacer cada
proyecto: un sistema de pagos y uno escolar pueden sacar 100 en las tres categorías y aun así romper la regla
más importante de su negocio.

La propuesta cumple dos condiciones:

1. **Las reglas son parte del proyecto analizado**: viven en su repositorio, versionadas con git, escritas por
   el equipo y verificadas con sus propias pruebas.
2. **No las decide la IA**: el resultado sale de evidencia (pruebas que pasan o fallan, líneas de código). La IA
   solo explica y sugiere, y lo que sugiere no cuenta en la calificación.

## 2. Dónde se sube: en el repositorio (oficial) o desde la app (de apoyo)

| Vía | Cómo | Cuándo usarla | ¿Cuenta como entregable? |
|---|---|---|---|
| **Repositorio** (principal) | Archivo `reglas_negocio.toml` en la raíz del repo, con commit como cualquier otro archivo | Siempre que se pueda | **Sí**: es la fuente de verdad |
| **App: Configuración → Reglas de negocio** | Subir el archivo, o escribir las reglas en un formulario | Mientras se redactan, o para probar antes de hacer commit | No: la app avisa "súbelo al repositorio" y ofrece descargarlo |

**Precedencia**: si el repositorio tiene `reglas_negocio.toml`, gana el del repositorio y la versión cargada en la
app se ignora (la app lo indica). Así nadie califica con reglas que no están en el código entregado.

### Por qué un archivo propio y no dentro de `.ia_voy.toml`

- `.ia_voy.toml` ya tiene una tabla `[reglas]` con otro significado (`ignorar = ["B101"]`: reglas de Bandit o
  Ruff silenciadas). Mezclar ambos confunde y, en TOML, `[reglas]` y `[[reglas]]` no pueden convivir.
- La pantalla de Configuración **reescribe** `.ia_voy.toml` completo al guardar: las reglas se borrarían.
- Las reglas las escribe el equipo (analistas, líder, QA); la configuración la genera la app. Archivos
  distintos, dueños distintos.

## 3. Formato y nomenclatura

### 3.1 Archivo

| Qué | Convención |
|---|---|
| Nombre | `reglas_negocio.toml` (minúsculas, guion bajo, exactamente así) |
| Ubicación | Raíz del repositorio. Si no está ahí, se busca en `docs/reglas_negocio.toml` |
| Formato | **TOML** UTF-8: el mismo de `.ia_voy.toml` y `pyproject.toml`, admite comentarios y Python lo lee sin dependencias (`tomllib`) |
| Tamaño | Máximo 256 KB y 200 reglas |
| Desde la app | Se acepta `.toml`; el nombre del archivo subido no importa, el contenido sí |

Se eligió TOML sobre las alternativas:

- **JSON**: no admite comentarios y es incómodo de escribir a mano.
- **YAML**: la indentación provoca errores y necesita una dependencia extra.
- **Excel o CSV**: no cabe bien el texto largo ni las listas, y no se revisa bien en un diff de git.
- **Markdown libre**: se lee bien, pero el sistema tendría que "adivinar" la estructura, y eso es justo lo que se
  quiere evitar.

### 3.2 Identificadores

| Elemento | Nomenclatura | Ejemplo |
|---|---|---|
| Regla | `RN-` + 3 dígitos, único en el archivo | `RN-001`, `RN-014` |
| Historia de usuario (opcional) | La que use el equipo en su tablero | `HU-07` |
| Marcador de prueba (principal) | `@pytest.mark.regla("RN-001")` (admite varias: `regla("RN-001", "RN-004")`) | ver §4 |
| Nombre de prueba (alternativa) | `test_rn001_<descripción>` | `test_rn002_cancelado_no_vuelve_a_pagado` |

### 3.3 Campos de cada regla

```toml
[proyecto]
nombre  = "Tienda escolar"          # obligatorio
version = "1.2"                     # opcional: versión del documento de reglas

[[regla]]
id          = "RN-001"                                   # obligatorio · ^RN-\d{3}$ · único
titulo      = "Montos con Decimal"                       # obligatorio · máx. 120 caracteres
descripcion = "Todo monto de dinero se calcula con Decimal; nunca con float."   # obligatorio
severidad   = "alta"                                     # obligatorio · alta | media | baja
rutas       = ["app/pagos/", "app/facturas/"]            # opcional · vacío = todo el repo
prohibido   = 'float\(.*(monto|precio|total)'            # opcional · regex que NO debe aparecer
historia    = "HU-03"                                    # opcional
responsable = "Equipo backend"                           # opcional
criterio    = "Dado un carrito de 3 artículos de $0.10, cuando se cobra, entonces el total es exactamente $0.30"  # opcional

[[regla]]
id          = "RN-002"
titulo      = "Un pedido cancelado no vuelve a pagado"
descripcion = "Una vez cancelado, el estado de un pedido no puede cambiar a 'pagado'."
severidad   = "alta"
# Sin patrón: la verifican las pruebas marcadas con @pytest.mark.regla("RN-002")

[[regla]]
id          = "RN-003"
titulo      = "Rutas de administración protegidas"
descripcion = "Toda ruta bajo /admin exige el decorador @requiere_admin."
severidad   = "media"
rutas       = ["app/admin/"]
obligatorio = '@requiere_admin'                          # opcional · regex que DEBE aparecer en cada archivo de rutas

[[regla]]
id          = "RN-004"
titulo      = "Descuento máximo"
descripcion = "Ningún descuento acumulado supera el 30 % del subtotal."
severidad   = "media"
ia          = true                                       # opcional · pedir además la opinión del asistente
```

| Campo | Tipo | Obligatorio | Para qué |
|---|---|---|---|
| `id` | texto `RN-###` | sí | Liga la regla con sus pruebas y sus hallazgos |
| `titulo` | texto | sí | Lo que se ve en tablas y hallazgos |
| `descripcion` | texto | sí | La regla completa, en lenguaje del negocio |
| `severidad` | `alta` / `media` / `baja` | sí | Cuánto resta si no se cumple |
| `rutas` | lista de carpetas o archivos | no | Dónde aplica el patrón; también acota la búsqueda del asistente |
| `prohibido` | expresión regular | no | Patrón que no debe aparecer en `rutas` |
| `obligatorio` | expresión regular | no | Patrón que debe aparecer en cada archivo `.py` de `rutas` |
| `ia` | `true` / `false` | no | Pide la evaluación de apoyo del asistente |
| `historia`, `responsable`, `criterio` | texto | no | Trazabilidad con el tablero y criterios de aceptación |

## 4. Cómo se liga cada regla con el código del proyecto

La forma principal es una **prueba**: la regla queda escrita dos veces, en lenguaje del negocio
(`reglas_negocio.toml`) y como código que la comprueba (pytest).

```python
# tests/test_pedidos.py
import pytest
from app.pedidos import Pedido, TransicionInvalida


@pytest.mark.regla("RN-002")
def test_cancelado_no_vuelve_a_pagado():
    pedido = Pedido(estado="cancelado")
    with pytest.raises(TransicionInvalida):
        pedido.marcar_pagado()
```

El marcador se registra una vez en la configuración de pytest del proyecto, para que pytest no muestre avisos:

```toml
# pyproject.toml (o la sección [pytest] de pytest.ini)
[tool.pytest.ini_options]
markers = ["regla(id): regla de negocio de reglas_negocio.toml que verifica esta prueba"]
```

## 5. Cómo lo verifica IA voy

Un paso nuevo, **"Verificando reglas de negocio"**, entre Radon y "Calculando score". El análisis pasa de 11 a
**12 pasos**.

| Nivel | Fuente | Cuenta en el score |
|---|---|---|
| **Pruebas** | Pruebas con `@pytest.mark.regla` (o nombre `test_rn###_…`), ejecutadas en el sandbox | Sí |
| **Patrón** | `prohibido` / `obligatorio` sobre `rutas`, en el backend (solo lee el código, como Bandit y Ruff) | Sí |
| **IA** | El asistente busca en el código del repo (RAG) y responde cumple / no cumple / no sé, con `archivo:línea` | **No**: queda como "sugerido por IA" hasta que una persona lo confirme |

Cada regla termina en un estado:

| Estado | Cuándo | Hallazgo |
|---|---|---|
| ✅ Cumple | Sus pruebas pasan y no rompe su patrón | — |
| ❌ No cumple | Falla una de sus pruebas o aparece el patrón | Severidad de la regla, con la prueba o `archivo:línea` |
| ⚠️ Sin verificar | No tiene pruebas ni patrón | Severidad baja: "regla declarada sin prueba" |
| 💬 Sugerencia IA | Solo para `ia = true` | Informativo, no resta |

## 6. Qué ve el usuario en la app

- **Configuración → Reglas de negocio** (pestaña nueva):
  - Origen de las reglas: "Repositorio · `reglas_negocio.toml` · commit `a1b2c3d`", "Cargadas en la app (no
    están en el repositorio)" o "Sin reglas".
  - Botones: **Descargar plantilla**, **Subir archivo**, **Editar en formulario**, **Validar**, **Descargar
    para el repo**.
  - Errores de validación con número de línea (por ejemplo: "línea 14: `RN-02` no cumple el formato `RN-###`").
- **Terminal del análisis**: el paso 12 muestra "8 reglas · 6 cumplen · 1 no cumple · 1 sin verificar".
- **Score**: categoría nueva **Reglas de negocio**. Si el proyecto no tiene reglas, la categoría no aparece y
  los pesos de las otras tres se reparten como hoy (nadie pierde puntos por no tener el archivo).
- **Vista "Reglas"**: matriz regla → estado → evidencia (prueba, `archivo:línea` o sugerencia de la IA).
- **Asistente**: recibe las reglas en su contexto. Al explicar un hallazgo puede decir "esto rompe RN-002" y
  proponer la prueba que falta.

## 7. Calificación

- `neg = 100 − Σ penalización` de las reglas que no cumplen o están sin verificar.
- Penalización por regla: alta 12 · media 6 · baja 2 (misma escala que Seguridad); "sin verificar" siempre 2.
- Pesos sugeridos cuando hay reglas: Seguridad 40 · Testing 25 · Buenas Prácticas 15 · Reglas de negocio 20.
  Se configuran en `.ia_voy.toml` (`[pesos] negocio = 0.20`).

## 8. Pasos para cada equipo

1. Descargar la plantilla desde Configuración → Reglas de negocio (o copiar el ejemplo de §3.3).
2. Escribir las reglas del negocio (salen de los requerimientos y criterios de aceptación de las historias).
3. Por cada regla, escribir al menos una prueba con `@pytest.mark.regla("RN-###")` o, si se ve en el código, un
   patrón `prohibido` / `obligatorio`.
4. Hacer commit de `reglas_negocio.toml` y las pruebas en la raíz del repo.
5. Correr un análisis: el paso 12 dice qué reglas cumplen, cuáles no y cuáles no tienen prueba.

## 9. Validaciones del archivo

| Error | Mensaje |
|---|---|
| TOML inválido | "reglas_negocio.toml no es TOML válido (línea N): …" |
| Falta `[proyecto] nombre` o un campo obligatorio de una regla | "RN-004: falta `severidad`" |
| `id` repetido o con otro formato | "RN-02 no cumple el formato RN-###" / "RN-001 está repetida" |
| Expresión regular inválida | "RN-001: `prohibido` no es una expresión regular válida" |
| Prueba marcada con una regla que no existe | Aviso: "tests/test_x.py::test_y usa RN-099, que no está en reglas_negocio.toml" |

Un archivo inválido **no detiene el análisis**: el paso 12 termina con el error y la categoría no se calcula.

## 10. Implementación (resumen técnico)

| Pieza | Dónde | Qué hace |
|---|---|---|
| Lectura y validación | `backend/app/analyses/reglas.py` (nuevo) | `tomllib` + validación de campos; reutiliza el estilo de `config_file.py` |
| Origen | Igual que `.ia_voy.toml` en `pipeline.py`: se lee del clon; si no existe, se usa la versión cargada en la app (tabla nueva en la BD) | Precedencia repo > app |
| Pruebas | Plugin de pytest de IA voy cargado en el sandbox con `-p ia_voy_reglas` | Escribe `reglas.json` (regla → pruebas → resultado) junto a `junit.xml` |
| Patrones | Backend, en paralelo con Bandit y Ruff | Resultados en tablas propias (`business_rule_results`), no en `findings` (ver ADR-003 §5) |
| Score | `scoring.py`: categoría `neg` opcional | Se excluye del promedio si no hay reglas |
| Frontend | Pestaña en Configuración, vista Reglas y paso 12 en `jobSteps.ts` | — |
| IA | Reutiliza el índice y el cliente LLM del asistente | Solo para `ia = true`, marcado como sugerencia |

**Plan sugerido**:

1. Archivo, validación y patrones (sin sandbox). **Hecho en el Sprint 7.**
2. Plugin de pytest y estados por regla.
3. Pestaña de carga en Configuración y vista Reglas.
4. Nivel de IA.
