# Guía: comprobar las reglas de negocio de un repo con IA voy

Para el equipo y para quien analice su propio proyecto. Explica cómo se usa el módulo de reglas de negocio, con qué repos
funciona bien y con cuáles no, y cómo saber si lo que dice es cierto. El detalle técnico está en
[PLAN_REGLAS_AUTOMATICO.md](PLAN_REGLAS_AUTOMATICO.md) y la historia de lo que costó en
[BITACORA_REGLAS_AUTOMATICAS.md](BITACORA_REGLAS_AUTOMATICAS.md).

## 1. Qué hace, en pocas palabras

Lee el documento de requisitos del repo, saca de ahí las reglas de negocio («el número de piloto no se repite», «con menos
de 24 h no hay reembolso»), escribe una prueba para cada una, la corre contra el código en un entorno aislado y dice por
regla, en una frase:

- 🟢 **se cumple**, y con qué se comprobó;
- 🔴 **no se cumple**, qué caso falla y dónde (con «Corregir con IA»);
- 🟡 **necesita una decisión** tuya o **no se pudo comprobar**, y por qué.

Solo pregunta lo que no puede decidir solo: dudas de sí o no («¿el límite incluye el valor exacto?») y, si el documento
se contradice, cuál de las dos reglas vale.

## 2. Cómo se usa (4 pasos)

1. **Nuevo análisis.** Pega la URL del repo y la rama. Si el repo trae su documento de requisitos (PDF o Word, de
   preferencia en `docs/`), verás «Encontré Requisitos.pdf»: al analizar, el programa saca las reglas y las guarda en el
   proyecto. No hay que descargar ni subir nada.
   - Si el repo no trae el documento: después de analizar, en **Configuración → Reglas de negocio**, súbelo (PDF o Word).
   - Si el repo trae su propio `reglas_negocio.toml` válido, se usa ese y el documento se ignora.
2. **Preguntas.** En Configuración → Reglas de negocio:
   - si el documento se contradice, elige **«Vale RN-…»** o **«Las dos valen»**;
   - contesta las dudas con **Sí** o **No**. El programa recuerda la respuesta para futuras importaciones.
3. **Preparar todo.** Un botón: aprueba las reglas sin dudas, arma el entorno de pruebas, escribe una prueba por regla, las
   corre, mide si cada prueba detecta un error puesto a propósito (prueba de fuerza) y pide una segunda opinión a la IA
   leyendo el código sin ver la prueba. Tarda de 3 a 8 minutos y sigue aunque cierres la pestaña.
   - Lo que pasa todos los controles se aprueba solo (marcado «aprobada por el programa», reversible en un clic).
   - Lo demás queda en **«Esperan tu revisión»** con el motivo y una recomendación.
   - Si quedan pruebas rotas o flojas, **«Volver a preparar»** las escribe de nuevo con lo que falló.
4. **Analiza otra vez** y abre la vista **Reglas** del reporte: ahí está el semáforo por regla.

## 3. Con qué repos funciona bien

| Rasgo del repo | Por qué importa |
|---|---|
| **Python con Flask, FastAPI o Django** | El programa reconoce sus rutas, modelos y roles; sin uno de esos frameworks solo quedan los patrones de texto. |
| **Documento de requisitos con texto** (PDF o Word) en el repo, de preferencia en `docs/` | Las reglas salen solas y cada una lleva su cita verificada. |
| **Reglas escritas con números y límites claros** («al menos el 50 %», «del 1 al 99», «máximo 2») | Menos dudas y pruebas más precisas. |
| **SQLite o base en memoria** | Las pruebas crean una base vacía por prueba en el sandbox. |
| **`requirements.txt` o `pyproject.toml` en la raíz** | El sandbox instala las dependencias sin ayuda. |
| **API JSON o páginas HTML con formularios** | Las dos sirven: en las de formularios (Flask con `render_template`, Django con `render`) el programa revisa la base en lugar del código de respuesta. |
| **La hora con `date.today()` / `datetime.now()` o con una función propia** | El reloj de las pruebas mueve las dos. |

Repos con los que se midió: `inventario-demo` (FastAPI, 18 reglas, 5 rotas a propósito), `reservas-demo` (Flask JSON,
15 reglas, 4 rotas y un documento que se contradice) y `iTsS4ma/f1-pitwall` (Flask con plantillas, 11 reglas, todas
cumplidas según las 43 pruebas de su autor). Resultados en la sección 7.

## 4. Con qué repos no funciona (o funciona a medias)

| Situación | Qué pasa | Qué hacer |
|---|---|---|
| **No hay documento de requisitos**, o solo está en Markdown, en el README o en una wiki | No se sacan reglas solas (solo se buscan PDF y Word). | Exporta el documento a PDF o Word y súbelo en Configuración; o escribe reglas una por una con «Escribe una regla con tus palabras». |
| **PDF escaneado** (imagen, sin texto) | Las citas quedan «sin comprobar» y nada se aprueba solo. | Usa un PDF con texto o un Word. |
| **Necesita PostgreSQL, MongoDB, Redis u otro servicio** para arrancar | El entorno de pruebas no arranca: las reglas quedan «sin verificar». | Por ahora no tiene solución (paso 7 del plan: docker-compose). |
| **Dependencias en una subcarpeta** sin marcador en la raíz | Las pruebas fallan al importar. | Limitación conocida (ver `repos-de-prueba.md`). |
| **La lógica está en el frontend, en tareas en segundo plano o en triggers de la base** | Las pruebas por HTTP no la alcanzan. | Revisa esas reglas a mano. |
| **Inicio de sesión con servicios externos** (OAuth, SSO) | El arnés no puede autenticar. | Hace falta un usuario de prueba local. |
| **Reglas de proceso** («el gerente firma cada lunes») | No se prueban: se marcan «fuera del código». | Es lo correcto. |
| **Gemini sin cuota o saturado** | La importación o «Preparar todo» se detienen; el análisis sigue. | Espera unos minutos y usa «Volver a preparar»: lo hecho se conserva. |
| **Repos grandes** (cientos de archivos) | Se leen los primeros archivos y el contexto de la IA se queda corto. | Funciona peor; revisa más reglas a mano. |

## 5. ¿Cómo sé si lo que dice está bien?

El resultado es **evidencia, no demostración**: una prueba revisa ejemplos, no todos los casos. Estas señales dicen cuánto
creerle:

1. **La regla salió del documento tal cual.** Cada regla trae su cita; si el programa no la encontró en el documento, la
   regla queda con una duda y no se aprueba sola. Revisa que las reglas sean las del documento (ni de más ni de menos):
   con documentos reales la IA a veces duplica una regla o incluye algo que no se comprueba en el código.
2. **Dos comprobaciones que no se ven entre sí dicen lo mismo.** Una regla se aprueba sola solo si su prueba es
   **fuerte** (detectó todos los errores puestos a propósito) y la **segunda opinión** (la IA leyendo el código sin ver la
   prueba) coincide. Si discrepan, la regla espera a una persona.
3. **La confianza por regla** (alta, media, baja) en el reporte: alta = pruebas y patrón; baja = solo patrón, o la prueba
   resultó floja o la segunda opinión discrepó.
4. **Un «no se cumple» trae el caso que falla.** Lee el mensaje: «se esperaba que se guardara el resultado del evento del
   30» es fácil de confirmar a mano. Si el mensaje no tiene sentido con lo que dice el documento, la prueba se equivocó: no
   la apruebes y usa «Volver a preparar».
5. **Si el repo ya trae sus propias pruebas de la regla** (`test_rn004_…` o `@pytest.mark.regla("RN-004")`), el análisis
   también las corre. Un «no se cumple» de la IA en una regla que el repo ya prueba nunca se aprueba solo: compara los dos
   resultados.
6. **Casos de control.** En «¿Se le puede creer al programa?» marca 3 o 4 reglas que sepas que se cumplen o se violan
   (prueba tú mismo en la app). El panel dice «acertó N de M». Si no acierta en las que conoces, no le creas en las demás.
7. **Mira el código cuando dude.** «Corregir con IA» muestra el cambio como diff antes de guardar; nunca modifica la regla
   ni su prueba.

Lo que **no** debes concluir: que una regla en verde está libre de errores en todos los casos, ni que una regla «sin
verificar» se viola. «Sin verificar» solo dice que el programa no pudo comprobarla.

## 6. Síntomas comunes y qué hacer

| Lo que ves | Causa probable | Qué hacer |
|---|---|---|
| «Reglas de negocio: después de analizar» aunque el repo trae el documento | El documento no es PDF ni Word, o está fuera de `docs/` con un nombre que no dice «requisitos», «reglas», «especificación»… | Súbelo en Configuración. |
| Muchas reglas «no se cumplen» de golpe | Pruebas mal armadas, casi nunca el código (con `f1-pitwall` pasó 8 de 11 veces antes de corregir el programa). | Lee 2 o 3 mensajes; si no tienen sentido, «Volver a preparar». |
| «Prueba rota» | La prueba no pudo preparar su caso (un dato mal armado, un campo que no existe). No dice nada del código. | «Volver a preparar». |
| «Prueba floja» | La prueba siguió pasando con el código cambiado a propósito: no comprueba la regla de verdad. | «Volver a preparar» la reescribe con los cambios que no notó. |
| «El entorno no arranca» | Falta una variable de entorno, un servicio o una dependencia. | Mira el mensaje de la prueba de humo; si es un servicio externo, ver sección 4. |
| La misma duda vuelve a salir | Se contestó escribiendo en la regla, no con los botones. | Contéstala con Sí/No una vez: se recuerda. |
| «Gemini alcanzó su límite» | Cuota del plan gratuito. | Espera y reintenta; el respaldo (Groq) solo cubre el asistente. |

## 7. Resultados medidos

| Repo | Reglas | Lo esperado | Lo que dio el programa |
|---|---|---|---|
| `inventario-demo` (FastAPI) | 18 + 1 de proceso | 13 se cumplen · 5 no | Se importan las 19 reglas solas al analizar; mediciones de «Preparar todo» en la bitácora §5b |
| `reservas-demo` (Flask JSON) | 17 (15 tras decidir) | 11 · 4, 2 contradicciones | 22 reglas importadas; 4 contradicciones marcadas y resueltas con 2 clics (las 2 reales) |
| `iTsS4ma/f1-pitwall` (Flask con plantillas) | 11 | 11 se cumplen | 11 reglas importadas y 1 duda; 9 se cumplen · 0 no · 2 pruebas rotas; 2 aprobadas solas y bien, 9 esperan revisión (antes de corregir el programa: 0 · 8 · 3 y 2 aprobadas mal) |

En todas las corridas medidas el programa **no aprobó solo ninguna regla con el veredicto equivocado** desde que se
agregó el freno de la sección 5, punto 5. Lo que sí varía entre corridas es cuántas reglas terminan esperando a una persona.
