# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versionado semántico.

## [Sin publicar] — Reglas de negocio verificables (docs/PROPUESTA_REGLAS_VERIFICABLES.md)

### Agregado
- Formato `reglas_negocio.toml` v2 (`tipo`, escenarios Dado/Cuando/Entonces, `estado`, `dudas`, `fuente`); el importador
  desde un documento saca reglas atómicas en borrador y una tabla de aprobación en Configuración las aprueba (solo las
  aprobadas se verifican).
- Mapa del proyecto (FastAPI, Flask y Django) y arnés de pruebas con Gemini, con prueba de humo en el sandbox. Detecta la
  carpeta del código en repos con `backend/`.
- Pruebas generadas por regla (con primera corrida, aprobación y exportación), matriz de permisos, evidencia de apoyo y
  prueba de fuerza (mutación dirigida) que avisa de pruebas débiles.
- Categoría `neg` (reglas de negocio) en el score, con peso 0 % por defecto: se ve en el reporte, el tablero, la
  tendencia, la comparativa y las exportaciones; solo mueve el global con un peso (`[pesos] negocio`).
- Las reglas del repositorio también se aprueban desde la tabla (se guardan en la copia de trabajo; hay que descargar el
  archivo y hacer commit). El análisis normal (pytest, cobertura, pip-audit) trabaja desde la carpeta del código si está en
  una subcarpeta (`backend/`).
- Las dudas de una regla se contestan con **Sí o No** en la tabla de aprobación: la respuesta queda en la descripción de la
  regla y el proyecto la recuerda; si una importación nueva trae la misma pregunta de la misma regla, se contesta sola.
- Resultado de las reglas en lenguaje normal (semáforo y una frase por regla), el `.toml` en «Avanzado» y «Escribe una regla
  con tus palabras» (la IA la redacta y entra en borrador).
- Casos de control opcionales («sé que se cumple / se viola») y panel de concordancia con el último análisis, con la
  confianza de cada regla.
- Lo que aprueba «Preparar todo» se marca «Aprobada por el programa» y se revierte a borrador en un clic.
- «El documento manda»: en una regla que el código no cumple, «Corregir con IA» propone el cambio en el código (no en la
  regla ni en su prueba) y lo muestra como diff antes de guardar.
- Los repos de prueba (`inventario_demo` y `reservas_demo`) tienen interfaz web en `/ui` y datos de ejemplo opcionales
  (`python -m inventario.datos_demo`, `python -m reservas.datos_demo`); sus errores sembrados siguen en la API.
- Primera corrida real con Gemini y `reservas-demo` (informe en `docs/CORRIDA_RESERVAS_DEMO.md`): las contradicciones se buscan en una
  segunda consulta sobre la lista final y por título (antes la IA numeraba mal), la memoria de dudas reconoce la misma pregunta
  redactada distinto con embeddings, y «Corregir con IA» recibe las demás reglas para no romperlas.
- Pruebas generadas por la IA de mayor calidad (medido con Gemini real en `reservas-demo`, 3 corridas por ronda): prompt que aísla la regla,
  evita cifras y formatos inventados y pregunta «¿pasaría igual sin la regla?»; validadores de rechazos sin 409, cifras ajenas, asserts
  sin comparación, nombres con letras raras y dos variables con el mismo usuario; y se insiste cuando dice «no implementada» con
  endpoints que existen y deja el código vacío. Falsos positivos de 3 a 1 o 2 y falsos negativos de 2 a 0 en 2 de 3 corridas.
- El importador detecta plazos ambiguos («un día antes», «días hábiles»…) y los convierte en dudas de sí o no; con la respuesta, la
  prueba generada usa el plazo correcto (RN-012 de reservas-demo: de 3 falsos positivos de 3 a 0).
- Repos de prueba propios (`inventario_demo`, `reservas_demo`) y scripts de medición (`backend/scripts/`).
- Eliminar un repositorio desde la lista (`DELETE /api/repos/{id}`): borra sus análisis, reglas, pruebas, enlaces, la copia
  de trabajo y los respaldos; con un análisis en curso responde 409. No toca el repositorio de GitHub.
- Subir el documento de requisitos arrastrándolo o eligiéndolo, con aviso de «Tipo de archivo no válido»; la tabla de
  aprobación muestra de qué capítulo y página (u hoja) salió cada regla y la ayuda explica cómo escribir un patrón (regex).

- «Documento para presentar»: las reglas como documento legible (HTML imprimible a PDF o Markdown) con resumen, guía de
  lectura, ejemplos Dado/Cuando/Entonces, dudas y fuente (`GET /api/projects/{id}/reglas/documento`). El `.toml` que
  genera la IA lleva al inicio una guía de lectura de sus campos.

- «Preparar todo» (Configuración → Reglas de negocio): aprueba las reglas sin dudas, prepara el entorno de pruebas, lo
  prueba, escribe y corre una prueba por regla y comprueba que detecten violaciones, sin pasos manuales
  (docs/PLAN_REGLAS_AUTOMATICO.md). Aprueba las pruebas que pasan y son fuertes; el filtro «Necesitan mi decisión» lista
  el resto.
- Cada regla sacada de un documento trae la `cita` textual que la respalda y el programa comprueba que esté en el
  documento, Word o PDF con texto (`cita_verificada`; agrega la dependencia `pypdf`); una regla sin cita o con una cita que
  no aparece queda con una duda. También avisa de frases que parecen reglas y no se extrajeron.
- Segunda lectura del código sin ver la prueba y contraste con su resultado (coincide / discrepa); «Preparar todo» solo
  aprueba solas las pruebas fuertes que coinciden.

### Cambiado
- Los mensajes de los hallazgos de Ruff y Bandit salen en español (`app/analyses/mensajes.py`); lo que no está en el
  catálogo conserva el original.
- Las reglas solo se importan de documentos PDF y Word (.docx); ya no de Markdown, texto ni .toml. Los PDF y Word del
  repositorio ahora sí se detectan en la copia de trabajo (antes solo se veían los de texto).
- Comparativa: los selectores se llaman «Base A» y «Base B». La IA ya no repite el título como descripción de una regla.
- `scores` y `weights` del API traen `neg` (puede ser `null` / 0).
- El sandbox instala también `[project].dependencies` de `pyproject.toml` y las librerías de pruebas de reglas; la red va
  bloqueada en las pruebas de reglas.

## [1.0.0] — 24 de noviembre de 2026 (Sprint 9, code freeze)

### Agregado
- Comparativa entre dos análisis del mismo repositorio: scores A/B y hallazgos nuevos y resueltos
  (`GET /api/repos/{id}/analyses`, `POST /api/diff`, pantalla Comparativa y botón "Comparar" en tablero y reporte).
- Respaldo del asistente: si Gemini responde 429/503 se prueban los modelos de `GEMINI_FALLBACK_MODELS` y al final
  Groq (Llama 3.3, `GROQ_API_KEY`). La pantalla del asistente muestra el modelo que respondió y el respaldo.
- QA manual con backend real (`docs/qa/qa-manual.md`) y prueba del sandbox con Docker (`docs/qa/sandbox-docker.md`).

### Cambiado
- El estado de servicios (`/api/health`) muestra el modelo principal, su respaldo, el túnel y el sandbox.

## [0.8.0] — 17 de noviembre de 2026 (Sprint 8)

### Agregado
- Compartir el reporte con un enlace público: contraseña opcional (scrypt, bloqueo tras 10 intentos), expiración
  y fragmentos de código opcionales. Vista pública sin sesión (`/r/{id}`).
- Exportación del reporte a JSON, HTML, Markdown y SARIF.
- Set de evaluación del asistente y bitácora de ajustes del prompt.

## [0.7.0] — 10 de noviembre de 2026 (Sprint 7)

### Agregado
- Reporte navegable: hallazgos con su fragmento de código, cobertura y complejidad; ignorar una regla desde el
  detalle del hallazgo recalcula el score sin re-analizar.
- Asistente IA con RAG sobre el código: fragmentos por función/clase (`ast`), embeddings de Gemini en SQLite,
  respuestas por streaming (SSE) con fuentes `archivo:línea` validadas.
- Paso 11 del análisis: indexar para el asistente.
- Editor Monaco: guardar con respaldo, re-análisis del archivo con Ruff y Bandit, correcciones automáticas de Ruff
  en modo diff.

## [0.6.0] — 3 de noviembre de 2026 (Sprint 6)

### Agregado
- Pasos 6 a 10 del análisis: pytest y coverage en el sandbox (simulados sin él), Ruff y Radon en el backend y el
  score ponderado por categoría con escala por tamaño. Se eligen los analizadores (al menos uno por categoría).
- Tablero con score global, KPIs por categoría, tendencia y atención prioritaria; score en Repositorios.
- API del reporte (`/api/report/{id}`), catálogo de reglas y documento de la fórmula del score.

### Cambiado
- Con `SANDBOX=off`, el entorno, las dependencias, pip-audit, pytest y coverage se simulan (sus hallazgos dicen
  "(simulado)").

## [0.5.0] — 27 de octubre de 2026 (Sprint 5)

### Agregado
- Pasos 3 a 5 del análisis: instalar las dependencias en el sandbox, Bandit sobre el código y pip-audit sobre las
  dependencias (ADR-002).
- Cada análisis guarda sus hallazgos de Seguridad; Repositorios los muestra por severidad.
- CI en cada PR (backend, frontend y e2e).

## [0.4.0] — 20 de octubre de 2026 (Sprint 4)

### Agregado
- Login con GitHub (OAuth) con el token cifrado (Fernet); selector de repos y ramas de la cuenta, incluidos privados.
- Análisis hasta el entorno aislado: clonado real, detección de lenguajes y `uv venv` en el sandbox o en el backend;
  terminal en vivo por WebSocket, cancelar y reintentar, jobs persistentes.
- Repositorios con sus análisis guardados, archivos del clon, configuración del proyecto (`.ia_voy.toml`) y equipos.
