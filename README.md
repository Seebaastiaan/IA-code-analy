# IA voy

Analizador de calidad de código **Python** para equipos. El usuario indica un repositorio de GitHub (URL +
rama); el backend lo clona, lo analiza y guarda el resultado en el historial del repositorio.

> Estado: **Sprint 7 (10 nov)** — Reporte de hallazgos, asistente IA (RAG) y editor. Pruebas: 162 de backend · 22 unitarias del frontend · 7 e2e.

## Objetivo del sprint

Ver cada hallazgo en un reporte navegable, que la IA explique el código con contexto real (RAG, paso 11 del análisis) y corregir los hallazgos desde el editor.

**Demo:** Abrir el reporte → detalle de un hallazgo con su código → "Preguntar a la IA" → respuesta en streaming con fuentes archivo:línea → abrir la fuente en el editor → aplicar la corrección de Ruff y ver subir el score.

**Criterio de aceptación:** Pruebas de backend, unitarias y e2e en verde; ignorar una regla recalcula el score al instante.

## Lo que hace la app

- Login con GitHub (OAuth); el token se guarda cifrado con Fernet y nunca llega al navegador
- Nuevo análisis: elegir un repo de la cuenta de GitHub (también privados) y su rama, o escribir la URL
- Clonado real y detección de lenguajes (solo Python); terminal en vivo por WebSocket; cancelar y reintentar
- Entorno aislado (`uv venv`) en el sandbox WSL2/Docker o, sin sandbox, en el backend
- Repositorios con sus análisis guardados, archivos del clon, configuración del proyecto (`.ia_voy.toml`) y equipo
- Dependencias del repo instaladas en el sandbox; Bandit revisa el código y pip-audit las dependencias
- Cada análisis guarda sus hallazgos de Seguridad y Repositorios los muestra por severidad
- Análisis completo en 10 pasos: pytest y coverage en el sandbox (simulados sin él), Ruff y Radon en el backend; se eligen los analizadores
- Score ponderado por categoría (pesos de Configuración / `.ia_voy.toml`) en Repositorios y en el tablero, con tendencia y hallazgos prioritarios
- Reporte navegable: hallazgos con su código, cobertura y complejidad; ignorar una regla recalcula el score
- Asistente IA (RAG con Gemini) con respuestas en streaming y fuentes archivo:línea; editor Monaco con correcciones automáticas

Llega en los siguientes sprints:

- Compartir el reporte y exportarlo (S8)
- Comparativa y respaldo del modelo (S9)

## Tareas del sprint

| # | Responsable | Equipo | Tarea | Archivos |
|---|---|---|---|---|
| 1 | Uriel Castorela | IA & Analizadores | Endpoint del asistente con streaming | assistant/router.py, llm.py |
| 2 | Diego Salinas | IA & Analizadores | Índice de embeddings del asistente | index.py, config.py, pyproject.toml, .env.example |
| 3 | Marco Espino | IA & Analizadores | Fragmentador del código | chunker.py |
| 4 | Carlos Jara | Backend & Plataforma | Paso 11: indexar para el asistente | jobs.py, fake.py, analysis/router.py |
| 5 | Dylan Martínez | Backend & Plataforma | API del editor: árbol, guardar con respaldo y correcciones | editor/router.py (retira repos/router.py) |
| 6 | Ana Cristina Luciano | Backend & Plataforma | Tablas del asistente e integración | db.py, main.py |
| 7 | Evelyn Martínez | QA | Pruebas del asistente | test_assistant.py, test_analysis.py, test_jobs.py |
| 8 | Luis Gabriel Manzano | QA | Pruebas del editor y unitarias | test_modules.py, chatStream.test.ts, patches.test.ts, suggestions.test.ts |
| 9 | Karen Peña | Front-End & UX | Editor Monaco y aplicar correcciones | features/editor |
| 10 | Emiliano Sánchez | Front-End & UX | Reporte, detalle del hallazgo e ignorar reglas | features/report, features/findings, SettingsForm |
| 11 | Andrea Nallely Peña Osorio | Front-End & UX | Pantalla del asistente y coordinación del sprint | features/assistant, routes, navigation, mocks, flujos.e2e.ts |

## Comandos

```bash
# Backend (http://localhost:8000, docs en /docs)
cd backend
uv sync --extra dev
cp .env.example .env       # llenar GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET (ver backend/README.md)
uv run uvicorn app.main:app --reload --port 8000
uv run pytest              # 162 pruebas
uv run python -m app.seed --login <tu-usuario-de-github>   # datos de demostración (después de entrar una vez)

# Frontend (http://localhost:5173; /api y /ws van al backend)
cd frontend
npm install
npm run dev
npm run build
npm test                   # 22 pruebas unitarias
npm run test:e2e           # pruebas e2e con Playwright (backend simulado)
```

`SANDBOX=wsl` (o `docker`) en `backend/.env` corre el entorno, las dependencias y pip-audit aislados del
backend; con `SANDBOX=off` el entorno se crea en el backend y pip-audit no corre.

Sin backend: crear `frontend/.env.development.local` con `VITE_USE_MOCKS=true` y `VITE_AUTO_LOGIN=true`
para usar el backend simulado (MSW) con la cuenta de prueba.

## Estructura

| Carpeta | Contenido |
|---|---|
| [backend/](backend) | API FastAPI + SQLite (detalle en [backend/README.md](backend/README.md)) |
| [frontend/](frontend) | React 19 + Vite + Tailwind, por módulos (`app → features → shared`) |
| [docs/](docs) | Especificación y estructura del frontend, ADRs y documentación técnica |
| [ia_voy_prototipo.html](ia_voy_prototipo.html) | Wireframes navegables originales |

## Equipos

| Equipo | Líder | Integrantes |
|---|---|---|
| Front-End & UX | Andrea Peña | Karen Peña, Emiliano Sánchez |
| Backend & Plataforma | Dylan Martínez | Carlos Jara, Ana Cristina Luciano |
| IA & Analizadores | Uriel Castorela | Marco Espino, Diego Salinas |
| QA (Pruebas Automatizadas) | Evelyn Martínez | Luis Gabriel Manzano |
