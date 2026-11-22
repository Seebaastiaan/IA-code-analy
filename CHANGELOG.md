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
- Repos de prueba propios (`inventario_demo`, `reservas_demo`) y scripts de medición (`backend/scripts/`).
- Eliminar un repositorio desde la lista (`DELETE /api/repos/{id}`): borra sus análisis, reglas, pruebas, enlaces, la copia
  de trabajo y los respaldos; con un análisis en curso responde 409. No toca el repositorio de GitHub.
- Subir el documento de requisitos arrastrándolo o eligiéndolo, con aviso de «Tipo de archivo no válido»; la tabla de
  aprobación muestra de qué capítulo y página (u hoja) salió cada regla y la ayuda explica cómo escribir un patrón (regex).

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
