# IA voy

Analizador de calidad de código **Python** para equipos. El usuario indica un repositorio de GitHub (URL +
rama); el backend lo clona, lo analiza y guarda el resultado en el historial del repositorio.

> Estado: **Sprint 9 (24 nov)** — Comparativa, respaldo del modelo y code freeze (v1.0). Pruebas: 195 de backend · 22 unitarias del frontend · 8 e2e.

## Objetivo del sprint

Demostrar la mejora real entre dos análisis (hallazgos nuevos y resueltos), que el asistente siga respondiendo si Gemini se satura y congelar el código en la versión 1.0.

**Demo:** Analizar → corregir desde el editor → re-analizar → comparativa con nuevos y resueltos → el asistente responde con el modelo de respaldo cuando Gemini da 429.

**Criterio de aceptación:** Pruebas de backend, unitarias y e2e en verde; cero errores críticos abiertos; etiqueta v1.0.

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
- Compartir el reporte con un enlace público (contraseña y expiración opcionales) y exportarlo a JSON, HTML, Markdown o SARIF
- Comparativa entre dos análisis (nuevos y resueltos) y respaldo del asistente (modelos de Gemini y Groq)

Llega en los siguientes sprints:

- Documentación, despliegue y entrega (S10)

## Tareas del sprint

| # | Responsable | Equipo | Tarea | Archivos |
|---|---|---|---|---|
| 1 | Uriel Castorela | IA & Analizadores | Respaldo Gemini → Groq | llm.py, assistant/router.py, config.py, .env.example |
| 2 | Dylan Martínez | Backend & Plataforma | Comparativa entre análisis | compare/router.py, main.py |
| 3 | Carlos Jara | Backend & Plataforma | Estado de servicios con el respaldo del modelo | analysis/router.py |
| 4 | Ana Cristina Luciano | Backend & Plataforma | Release v1.0 y CHANGELOG | CHANGELOG.md, pyproject.toml |
| 5 | Marco Espino | IA & Analizadores | QA manual con backend real | docs/qa/qa-manual.md |
| 6 | Diego Salinas | IA & Analizadores | Prueba del sandbox con Docker | docs/qa/sandbox-docker.md |
| 7 | Luis Gabriel Manzano | QA | Pruebas de comparativa y del respaldo | test_compare.py, test_assistant.py |
| 8 | Evelyn Martínez | QA | Batería e2e completa | flujos.e2e.ts |
| 9 | Karen Peña | Front-End & UX | Comparar desde el reporte y respaldo en el asistente | ReportHeader, AssistantPage |
| 10 | Emiliano Sánchez | Front-End & UX | Comparar desde el tablero y estado de servicios | DashboardPage, mocks/fixtures/health.ts |
| 11 | Andrea Nallely Peña Osorio | Front-End & UX | Pantalla de comparativa y coordinación del sprint | ComparePage, routes, navigation, mocks |

## Comandos

```bash
# Backend (http://localhost:8000, docs en /docs)
cd backend
uv sync --extra dev
cp .env.example .env       # llenar GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET (ver backend/README.md)
uv run uvicorn app.main:app --reload --port 8000
uv run pytest              # 195 pruebas
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
