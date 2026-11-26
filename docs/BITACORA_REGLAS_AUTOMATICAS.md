# Bitácora de las reglas automáticas: cambios, tropiezos y conceptos nuevos

Rama `sprint-9`, trabajo del 22 de noviembre de 2026 (commits `76d62da` a `a03642a`). Complementa a
[PLAN_REGLAS_AUTOMATICO.md](PLAN_REGLAS_AUTOMATICO.md) (el plan por pasos) y a
[CORRIDA_RESERVAS_DEMO.md](CORRIDA_RESERVAS_DEMO.md) (la medición con Gemini real). Aquí está lo que pasó, en el orden en que se aprendió.

## 1. En una página

- **Qué se logró.** El programa ya no exige conocer el `reglas_negocio.toml`: lee el documento de requisitos, pregunta solo lo que no
  puede decidir, escribe y corre las pruebas, y dice en lenguaje normal qué regla se cumple, cuál no y por qué.
- **Qué se midió.** Con Gemini real y el repo `reservas-demo` (4 reglas rotas a propósito): se detectan las 2 contradicciones del documento,
  las pruebas escritas por la IA bajaron de 3 falsos positivos y 2 falsos negativos a 0 a 2, y la aprobación automática no aprobó nunca una regla incumplida.
- **Qué no se resolvió.** Las pruebas de la IA todavía varían entre corridas, solo se midió un modelo y un repo, y falta el paso 7
  (caja negra con docker-compose y base de datos real).

## 2. Conceptos nuevos

| Concepto | Qué es | Dónde está |
|---|---|---|
| **El programa trabaja por el equipo** | Principio: la persona ve lenguaje normal y el programa pregunta solo en 3 casos (documento ambiguo, código y documento en conflicto, no pudo comprobar). El TOML queda en «Avanzado». | `PLAN_REGLAS_AUTOMATICO.md` |
| **Preparar todo** | Un botón que encadena aprobar reglas, arnés, prueba de humo, pruebas, corrida, prueba de fuerza y lectura del código. | `useAutoVerify.ts`, `AutoVerifyCard.tsx` |
| **Cita verificada** | La IA copia la frase del documento que respalda cada regla y el programa la busca (Word y PDF con texto; tolera un par de palabras distintas). Sin cita encontrada, la regla queda con una duda y no se aprueba sola. | `reglas_importar.quote_found` |
| **Revisión independiente** | Una segunda consulta lee el código sin ver la prueba y su veredicto se contrasta con el de la prueba: «coincide» o «discrepa». | `reglas_evidencia.py`, `crosscheck` |
| **Aprobación por el programa** | Solo se aprueba sola una prueba fuerte (prueba de fuerza) que coincide con la lectura del código. Queda marcada «Aprobada por el programa» (`aprobada_por = "programa"`) y se revierte en un clic. | `reglas.py`, `RulesApprovalTable.tsx` |
| **Duda de sí o no con memoria** | Cada duda se contesta con Sí o No; la respuesta se anota en la descripción de la regla y se guarda por proyecto. Una importación nueva con la misma pregunta se contesta sola, aunque la IA la redacte distinto (comparación por significado con embeddings). | `reglas_respuestas.py`, tabla `business_rule_answers` |
| **Plazos ambiguos como dudas** | «Un día antes», «el día anterior», «la víspera», «al día siguiente», «una semana o un mes antes» y «días hábiles» se detectan de forma fija y se preguntan. | `reglas_importar.TIME_AMBIGUITIES` |
| **El documento manda** | Una regla que el código no cumple ofrece «Corregir con IA»: la IA cambia el código (nunca la regla ni su prueba) y se ve como diff en el editor sin guardar nada. Recibe las demás reglas para no romperlas. | `pruebas.fix_code_for_rule` |
| **Casos de control y concordancia** | El equipo marca «sé que se cumple / se viola» en reglas que conoce (opcional, no cambia resultados) y el panel compara con el último análisis: «acertó N de M». | `reglas_concordancia.py`, `ConcordanceCard.tsx` |
| **Confianza por regla** | Alta, media o baja según cómo se comprobó (pruebas y patrón, pruebas, patrón) y ajustada por la prueba de fuerza. | `reglas_concordancia.confidence` |
| **Semáforo en lenguaje normal** | Una frase por regla: 🟢 con qué se comprobó, 🔴 qué caso falla y dónde, 🟡 qué falta decidir. | `utils/rules.ts` (`plain`) |
| **Regla con tus palabras** | Se escribe una regla en una frase y la IA la redacta como regla verificable, en borrador. | `POST …/reglas/redactar` |
| **Segunda pasada de contradicciones** | Una consulta aparte busca contradicciones sobre la lista final de reglas, que numera el programa. | `reglas_importar.second_pass` |
| **Calidad de las pruebas generadas** | Validadores que rechazan pruebas con fallos conocidos (ver sección 4) y un prompt que pide aislar la regla y preguntarse si el assert pasaría igual sin ella. | `reglas_pruebas.quality_errors` |

## 3. Cambios por área

**Importar el documento**
- Citas textuales verificadas contra el documento; avisos de frases que parecen reglas y no se extrajeron.
- Contradicciones por título y en una segunda consulta (antes numeradas por la IA).
- Regla repetida en dos secciones: se pide una sola; reglas de proceso («la recepción llama a…») se extraen con tipo `proceso`.
- Plazos ambiguos convertidos en dudas.

**Aprobar y verificar**
- Tabla de aprobación con filtro «Necesitan mi decisión», dudas de sí o no y revertir la aprobación del programa.
- Preparar todo, prueba de fuerza usada en la confianza, panel de concordancia.
- Resultado con semáforo; el `.toml`, la plantilla y la ayuda de regex dentro de «Avanzado» (cerrado salvo que haya un error).

**Corregir**
- «Corregir con IA» para reglas incumplidas, con el contexto de las demás reglas y la orden de cambiar lo mínimo.

**Pruebas generadas por la IA**
- Prompt: aislar la regla, no inventar cifras ni formatos, revisar asunto y cuerpo del correo, ubicar el reloj dentro del plazo, códigos 401/423/429
  para credenciales y bloqueos.
- Validadores: rechazos sin 409, cifras que no están en la regla, `assert` sin comparación, nombres con letras de otro alfabeto, dos variables
  con el mismo `como("rol")`.
- Reintento cuando dice «no implementada» con endpoints que sí existen y deja el código vacío.

**Repos de prueba** (`inventario-demo` y `reservas-demo`, ahora públicos)
- Interfaz web sin compilar en `/ui` (cada rol ve solo lo que su matriz de permisos permite), datos de ejemplo (`datos_demo`) y bandeja de correos
  de demostración. Los errores sembrados siguen en la API: la interfaz no los esconde ni los arregla.

**Frontend y pruebas**
- 3 e2e nuevos de Playwright (23 en total) y 61 pruebas unitarias; suite del backend: 510 pasan.

## 4. Tropiezos y retrasos (lo que costó tiempo)

Cada punto dice qué pasó, cómo se descubrió y cómo quedó.

| # | Tropiezo | Cómo se vio | Resolución |
|---|---|---|---|
| 1 | **El mock rechazaba `aprobada_por`.** Tras «Preparar todo» el archivo quedaba inválido y la tabla desaparecía. | Un e2e nuevo | Campo agregado al mock |
| 2 | **El panel de concordancia no se refrescaba** al agregar reglas. | El mismo e2e | La consulta incluye una versión de las reglas |
| 3 | **«Avanzado» se cerraba solo** mientras se escribía el `.toml`. | Playwright | Estado controlado; se abre solo ante un error |
| 4 | **`vitest` no corre con `npm test`** en este equipo (falla con «Cannot read properties of undefined (reading 'config')»). | Todos los archivos de prueba, también sin los cambios | Funciona con `npx vitest run --pool=vmThreads`; la causa de fondo no se investigó |
| 5 | **Las ediciones con salto de línea fallaban a ratos** (Windows y finales de línea). | Scripts de parche que no aplicaban | Edición con herramienta o scripts por archivo |
| 6 | **Dos tests de mapa se rompieron** al agregar la interfaz: `inventario_demo` tiene 2 rutas más y el script de datos de reservas usaba `datetime.now()`. | Suite completa | Cifra del test actualizada; el script usa `reloj.ahora()` |
| 7 | **La primera corrida real se colgó 15 minutos**: se usó el cliente de pruebas sin mantener vivas las tareas en segundo plano. | El análisis nunca terminaba | Servidor real (`uvicorn`) y cliente HTTP |
| 8 | **Un tiempo de espera de Gemini** (68 s) en la primera importación del PDF. | 503 `llm_unavailable` | Reintento; la segunda vez tardó 23 s |
| 9 | **La IA numeraba mal las contradicciones** y marcaba un par equivocado; con una sola consulta salían en 3 de 5 corridas y la comisión del 10 % nunca. | Comparación con `ESPERADO.md` | Por título y segunda pasada: 4 de 4 corridas |
| 10 | **La memoria de dudas casi no reconocía** la misma pregunta redactada distinto (1 de 6 pares). | Reimportaciones reales | Embeddings: 3 de 3 reimportaciones |
| 11 | **«Corregir con IA» borró la excepción premium** al arreglar el reembolso. | Revisión del diff | Recibe las demás reglas: `>` a `>=` exacto 3 de 3 |
| 12 | **«Regenerar» no regeneraba**: reutilizaba las pruebas guardadas y devolvía los mismos resultados en 11 s. | Resultados idénticos a la corrida anterior | La medición borra las pruebas antes de generar |
| 13 | **Las pruebas a mano del repo tenían otra numeración** que el importador y se enlazaban a reglas que no eran. | Resultados que no cuadraban | Se quitaron del clon local para medir; las cifras del primer reanálisis no son confiables |
| 14 | **Pruebas sin generar**: la IA decía «no implementada» con endpoints existentes y devolvía código vacío (1 a 2 reglas por corrida). | `escritas: 16 de 18` | Reintento: 18 de 18 en las 3 últimas corridas |
| 15 | **Un nombre con letra árabe** (`reloj.ir_ا`) rompía una prueba. | Una prueba rota | Validador de nombres |
| 16 | **El falso positivo del recordatorio** (3 de 3): la prueba ponía el reloj 25 h antes y el código avisa a las 24 h. Era una ambigüedad del documento. | Mensaje de la prueba | Plazos ambiguos como dudas: 0 de 3 después de contestar |
| 17 | **Línea citada en `ESPERADO.md`** de `reservas-demo` se movió (`app.py:190` a `:194`) al agregar la interfaz. | Revisión manual | Actualizada |

## 5. Resultados medidos (Gemini 3.5 Flash Lite, `reservas-demo`)

| Medida | Antes | Después |
|---|---|---|
| Contradicciones reales detectadas | 3 de 5 corridas (la comisión, nunca) | 4 de 4 corridas, las dos |
| Reglas que llegan a tener prueba | 16 a 17 de 18 | 18 de 18 |
| Pruebas: aciertos / falsos positivos / falsos negativos | 12 / 3 / 2 (1 corrida) | 13 a 15 / 1 a 2 / 0 a 2 (3 corridas) |
| Reconocer la misma duda redactada distinto | 1 de 6 | 3 de 3 reimportaciones |
| «Corregir con IA» sin romper otra regla | 0 de 1 | 3 de 3 |
| Recordatorio (plazo ambiguo) | falso positivo 3 de 3 | pasa 3 de 3 tras contestar la duda |
| Aprobaciones automáticas incorrectas | — | 0 de 5 (todas eran reglas que sí se cumplen) |

## 5b. «Preparar todo» de punta a punta con `inventario-demo` (Gemini 3.5 Flash Lite, sandbox WSL)

Medido con `backend/scripts/medir_preparar.py`: copia el demo sin `referencia/` ni sus pruebas escritas a mano, carga las 18 reglas
(5 rotas a propósito), corre «Preparar todo» en el servidor y un análisis, y compara con `ESPERADO.md`. Unos 7 minutos por corrida.

| Ronda | Pruebas que aciertan | Falsos positivos / negativos | Aprobadas solas | Aprobadas mal | Reglas rotas que llegan al reporte |
|---|---|---|---|---|---|
| 1 · flujo en el servidor (1 corrida) | 14 de 18 (4 rotas) | 0 / 0 | 2 | 0 | 0 de 5 |
| 2 · aprobar las que fallan y coinciden; corregir las rotas con su error (2 corridas) | 17 · 17 | 0 · 1 / 0 · 0 | 4 · 6 | 0 · 0 | 2 · 4 de 5 |
| 3 · sin mutar el «no existe» (404); leer el código tras reescribir (2 corridas) | 16 · 17 | 1 · 1 / 0 · 0 | 9 · 10 | 0 · 0 | 5 · 5 de 5 |

Qué se encontró en cada ronda:

1. **Ninguna regla rota podía aprobarse sola.** La prueba de fuerza solo se mide a las pruebas que pasan y la aprobación pedía «fuerte»,
   así que las 5 rotas quedaban «sin verificar» aunque la prueba fallaba y la lectura del código coincidía. Ahora una prueba que falla se
   aprueba sola si la lectura del código tampoco encuentra la regla completa.
2. **Las pruebas rotas eran errores de la IA al preparar el escenario** (esperaba 201 de una venta que responde 200, compraba un producto
   con receta, mandaba un `Decimal` a JSON). Al reescribirlas se le da su código y el error: de 4 rotas, 1 a 0 por corrida.
3. **La prueba de fuerza castigaba pruebas buenas.** Quitar el `raise HTTPException(404, "No existe el producto")` de `obtener` sobrevivía a
   las pruebas de RN-011, 012 y 013, que no tienen por qué notarlo. Ese cambio solo se hace si la regla habla de existencia.
4. **La red de seguridad funcionó:** el falso positivo de RN-016 (la prueba falla y la regla sí se cumple) salió «discrepa» y no se aprobó.

Queda: 4 o 5 reglas con fuerza «parcial» (RN-005, 009, 010, 013, 014) y RN-004 sin cambios que inyectar esperan a una persona; el reporte
ahora dice «su prueba pasa (no notó todas las violaciones…), pero todavía no cuenta» en lugar de «sin patrón ni pruebas».

## 5c. Con un repo como cualquier otro: `reservas-demo` sin arnés ni pruebas

Los demos ya no traen la clave (pruebas a mano, `conftest.py` listo, reglas resueltas): la IA tiene que escribir el arnés. Se midió
`reservas-demo` (Flask, 15 reglas, 4 rotas) con las reglas de la clave para comparar con `ESPERADO.md`.

| Corrida | Arnés | Pruebas que aciertan | Aprobadas solas | Aprobadas mal | Rotas que llegan al reporte |
|---|---|---|---|---|---|
| 1 | bien al primer intento | 12 de 15 | 8 | 0 | 2 de 4 |
| 2 | 401: no autenticaba (modelo de respaldo) | — | — | — | se detuvo |
| 3 · 4 (arnés corregido con el error de la prueba de humo) | bien | 4 · 6 (8 pruebas rotas: no daba el id del usuario) | 1 · 4 | 0 · 0 | 0 · 0 de 4 |
| 5 · 6 (`como(rol).id` exigido) | bien · rechazado por una comprobación demasiado estricta | 5 (4 falsos positivos, ninguno aprobado) · — | 2 · — | 0 | 1 · — de 4 |

| 7 · 8 · 9 | bien · bien con la corrección · `'dict' object is not callable` | 4 · 9 · — | 2 · 5 · — | 0 | 0 · 1 · — de 4 |
| 10 · 11 · 12 (roles separados exigidos) | token repetido entre pruebas · igual · bien con la corrección | — · — · 7 | — · — · 6 | 0 | — · — · 1 de 4 |

En las corridas 7 a 12 el modelo principal (Gemini 3.5 Flash Lite) estuvo saturado toda la tarde: el arnés y las pruebas los escribió el
modelo de respaldo (Gemini 3.1 Flash Lite), más débil. Con él, la mitad de las veces el arnés no pasa la prueba de humo ni con una
corrección.

Correcciones que salieron de aquí: el arnés de la IA se reescribe una vez con el error de su prueba de humo; la prueba de humo acepta un
cliente nuevo del mismo usuario (mismo estado, aunque su clase se defina dentro de `como`) y exige `como(rol).id` al arnés de la IA; las
pruebas usan `como(rol).id` cuando una ruta pide el usuario; la prueba de humo exige que dos roles den clientes distintos (en la corrida 7
`como` devolvía el mismo cliente para todos los roles y, al crear un servicio como admin, la prueba del cliente quedaba autenticada como admin).

**Lectura honesta:** en las 11 corridas medidas (`inventario-demo` y `reservas-demo`) el programa nunca aprobó solo una regla con el
veredicto equivocado. Pero con un repo sin arnés el resultado depende mucho del primer arnés que escribe la IA, y cuando Gemini está saturado
y responde el modelo de respaldo, baja bastante. Con `reservas-demo` limpio, la mayoría de las reglas todavía terminan esperando a una
persona. Falta medir con el modelo principal disponible (o con otro modelo más fuerte) para saber cuánto se debe al modelo de respaldo.

## 6. Pendientes y riesgos

- **Variación entre corridas** (mitigado: «Preparar todo» escribe de nuevo las pruebas que no coinciden con la lectura del código; falta medir cuánto ayuda con Gemini real). Los falsos negativos del empalme de profesionales y del bloqueo de cuenta aparecen en 1 de cada 3 corridas;
  de vez en cuando una prueba sale rota. Por eso nada se aprueba sin prueba de fuerza y lectura del código.
- **Un solo modelo.** `inventario-demo` ya se midió de punta a punta (§5b); falta otro modelo y volver a medir `reservas-demo` con el flujo nuevo.
- **Paso 7: caja negra** con docker-compose y base de datos real. Un repo que necesite servicios externos no se podrá verificar bien.
- ~~**La revisión independiente** todavía no entra en la confianza por regla.~~ Ya entra (coincide sube, discrepa baja a «baja»).
- **Plazos ambiguos:** la lista es corta y fija; «pronto», «al cierre» o «cada mes» no se detectan.
- **PDF escaneado** (sin texto): sus citas quedan «sin comprobar».
- **`vitest`:** con `npm test` desde Git Bash falla con «reading 'config'»; desde PowerShell corre bien (72 pruebas). Es la ruta o
  la terminal, no el código.
- **Publicación:** los repos de prueba son públicos y su historial muestra un correo institucional; la carpeta `referencia/` (las respuestas
  correctas) también es pública.
- **Rama `sprint-9`:** subida a GitHub (23 de noviembre).
- **Reescribir tras una discrepancia puede empeorar la prueba** (§7): en `f1-pitwall` dos pruebas que pasaban se reescribieron por
  discrepar con la segunda opinión y salieron «no cumple» equivocado. No se aprobaron (el freno funciona), pero quedan para revisión.
- **Documentos en Markdown:** no se buscan (solo PDF y Word). Muchos repos escolares tienen la documentación en `docs/*.md`.

## 7. 23 de noviembre: sin pasos manuales y el primer repo ajeno (`iTsS4ma/f1-pitwall`)

Lo que se pidió: que no haya que descargar las reglas ni subirlas en Configuración, decidir las contradicciones con botones y
comprobar el flujo con un repo que no hicimos nosotros. Guía para el equipo: [GUIA_REGLAS_DE_NEGOCIO.md](GUIA_REGLAS_DE_NEGOCIO.md).

### Cambios

- **Las reglas salen solas al analizar** (`app/projects/reglas_auto.py`): si el repo no trae `reglas_negocio.toml` y el proyecto no
  tiene reglas, el análisis lee el documento de requisitos mientras corren los analizadores y las guarda en el proyecto, en
  borrador. Nunca pisa lo que el equipo guardó; si la IA falla, el análisis sigue. El paso 10 lo dice.
- **Contradicciones con botones** («Vale RN-…» / «Las dos valen»): la regla que no vale se quita del archivo junto con sus otras
  marcas. Una importación con contradicciones ya se puede guardar.
- **Apps de páginas HTML** (Flask con plantillas, Django con `render`): el mapa las marca (`html`), las pruebas revisan la base en
  lugar del código de respuesta, incluyen el caso válido que sí se guarda y usan las claves exactas de las constantes del código
  (van en el prompt). Una prueba que decide un rechazo con `assert r.status_code` se rechaza y se reescribe.
- **Reloj de la hora del sistema**: `Reloj(…, sistema=True)` mueve también `date.today()` y `datetime.now()` (time_machine, en
  hora local). El arnés no puede reemplazar `date`/`datetime` del proyecto con monkeypatch.
- **Dudas de límites que el documento ya contesta** («25 % o más», «al menos el 50 %», «del 1 al 99») se quitan sin IA.
- **En `docs/` cuenta cualquier PDF o Word** como documento de requisitos.
- **Un «no cumple» de la IA no se aprueba solo** si el repo trae pruebas propias de esa regla.
- La memoria de respuestas también compara por significado cuando las reglas salen solas.
- Arnés de apps de formularios: CSRF de Flask-WTF desactivado en pruebas y `como(rol)` con el login de la app o la sesión.

### Tropiezos

| # | Tropiezo | Cómo se vio | Resolución |
|---|---|---|---|
| 18 | **Había que descargar las reglas y subirlas en Ajustes** en cada repo; la app además pedía «descárgalas y súbelas al repo». | Lo señaló el equipo | Importación automática al analizar |
| 19 | **Resolver contradicciones exigía editar el TOML** en «Avanzado». | Prueba en Chrome con `reservas-demo` | Botones; con `reservas-demo` se resolvieron las 4 marcas con 2 clics |
| 20 | **El paso 10 decía «sin reglas declaradas»** justo cuando las estaba sacando; a veces salía el resumen normal porque la lectura terminaba antes del paso (carrera de tiempos). | Terminal del análisis y una prueba que fallaba 1 de cada 3 | Texto propio mientras se importan, sin depender de quién termina primero |
| 21 | **Se creyó que la memoria no aplicó 2 respuestas**; esas dudas se habían resuelto escribiendo en la regla, no con los botones, y la única candidata era otra pregunta (similitud 0,874 contra 0,88). | Revisión de `business_rule_answers` | El umbral se dejó igual; la importación automática ahora también usa embeddings |
| 22 | **`Documentacion.pdf` no se detectaba**: el nombre no decía «requisitos». | Nuevo análisis de `f1-pitwall` | En `docs/` cuenta cualquier PDF o Word |
| 23 | **8 de 11 reglas «no se cumplen» con un código correcto**: la app rechaza volviendo a mostrar la página (200) o redirigiendo (302) y las pruebas esperaban 400/409/422. | Las 43 pruebas del autor pasaban | Modo HTML: revisar la base, no el código |
| 24 | **Dos reglas se aprobaron solas como «no cumple»** porque la segunda opinión dijo «no encontrada» / «parcial»: no le llegaron los fragmentos con la lógica. | Su propio resumen («los fragmentos no contienen la lógica») | Freno: no se aprueba solo un «no cumple» si el repo trae pruebas propias de la regla |
| 25 | **Claves inventadas** («75%», «0.5», «1v» en vez de `"75"`, `"menos2"`): las constantes estaban al inicio del módulo, fuera de los fragmentos. El formulario no guardaba y la prueba decía «no cumple». | Mensajes «el resultado no fue guardado» | Constantes en MAYÚSCULAS en el prompt; el caso válido se comprueba con `preparar` (sale como prueba rota, no como «no cumple») |
| 26 | **Pruebas flojas que no notaban nada** (0 de 5, 0 de 8 cambios): solo revisaban que el caso malo no se guardara, y eso también pasa si la app no guarda nada o lo rechaza todo. | Prueba de fuerza | Toda prueba de rechazo incluye el caso válido que sí se guarda: después, 9 de 10 y 7 de 8 |
| 27 | **El reloj no controlaba `date.today()`**: la app no tiene función propia de la hora; una prueba de «eventos ya corridos» falló con el código bien. | Mensaje de la prueba (fecha del 30 tratada como futura) | `Reloj(…, sistema=True)` con time_machine en hora local (al principio movía al día anterior: tomaba la fecha como UTC) |
| 28 | **El arnés reemplazó `date` del proyecto con el reloj**: `'Reloj' object has no attribute 'fromisoformat'`. | Prueba rota | Revisión sin IA que lo rechaza |
| 29 | **Dudas que el documento ya contestaba** (3 de 3 en `f1-pitwall`). | Preguntas de la importación | Filtro sin IA: 0 de 3 después (queda 1 duda legítima: el mismo día del evento) |
| 30 | **Cada edición del backend reinicia el servidor** (`--reload`) y corta «Preparar todo» a la mitad: se perdieron 2 corridas. | Corrida detenida en «Segunda opinión» | Medir sin tocar `app/` hasta que termine |
| 31 | **Gemini alcanzó su límite** al indexar para el asistente durante las corridas. | Terminal del análisis | No detiene el análisis; se reintenta al abrir el asistente |
| 32 | **Una constante `UNITS` repetida** en el importador: la nueva quedaba tapada por la de más abajo. | Prueba que no pasaba | Renombrada |

### Resultados con `iTsS4ma/f1-pitwall`

Flask con plantillas, SQLite con `sqlite3` directo, 11 reglas en `docs/Documentacion.pdf` y 43 pruebas del autor que pasan: lo
esperado es **11 se cumplen**. Gemini 3.5 Flash Lite, sandbox WSL.

| Corrida | Reglas importadas | Dudas | Ejecutar las pruebas | Aprobadas solas | Aprobadas mal |
|---|---|---|---|---|---|
| Antes de los cambios | 11 de 11 (una por cada RN del documento) | 3 (las 3 ya contestadas en el documento) | 0 cumplen · 8 no cumplen · 3 rotas | 2 | **2** (RN-001 y RN-002 como «no cumple») |
| Modo HTML (base en lugar de código) | — | — | 6 · 2 · 3 | — | — |
| + caso válido y valores exactos | — | — | 8 · 0 · 3 (tras reescribir) | 1 | 0 |
| Corrida limpia con todo (importación incluida) | 11 de 11 | 1 (legítima) | 9 · 0 · 2 | 2 (RN-003 y RN-004, fuertes y con segunda opinión) | 0 |

En la corrida limpia, al reescribir las pruebas que discrepaban con la segunda opinión, RN-005 y RN-007 salieron «no cumple»
equivocado (no se aprobaron). Quedan para revisión 9 reglas: lo más común es «prueba floja» o que la segunda opinión «no encontró» el
código. La revisión que impide reemplazar `date` (tropiezo 28) entró después de esa corrida.

**Lectura honesta:** el programa ya no da falsos «no cumple» de golpe con apps de formularios y no aprobó nada mal, pero con un repo
ajeno la mayoría de las reglas todavía termina esperando a una persona.
