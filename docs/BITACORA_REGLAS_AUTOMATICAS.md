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

## 6. Pendientes y riesgos

- **Variación entre corridas.** Los falsos negativos del empalme de profesionales y del bloqueo de cuenta aparecen en 1 de cada 3 corridas;
  de vez en cuando una prueba sale rota. Por eso nada se aprueba sin prueba de fuerza y lectura del código.
- **Un solo modelo y un solo repo.** Falta repetir la medición con `inventario-demo` (18 reglas, 5 rotas) y con otro modelo.
- **Paso 7: caja negra** con docker-compose y base de datos real. Un repo que necesite servicios externos no se podrá verificar bien.
- **La revisión independiente** todavía no entra en la confianza por regla.
- **Plazos ambiguos:** la lista es corta y fija; «pronto», «al cierre» o «cada mes» no se detectan.
- **PDF escaneado** (sin texto): sus citas quedan «sin comprobar».
- **`vitest`:** hay que investigar por qué falla con `npm test` en este equipo.
- **Publicación:** los repos de prueba son públicos y su historial muestra un correo institucional; la carpeta `referencia/` (las respuestas
  correctas) también es pública.
- **Rama `sprint-9`:** todo está commiteado y sin subir a GitHub.
