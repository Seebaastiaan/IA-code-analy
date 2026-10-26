# IA voy

Analizador de calidad de código **Python** para equipos. El usuario indica un repositorio de GitHub (URL +
rama); el backend lo clona, lo analiza y guarda el resultado en el historial del repositorio.

> Estado: **Sprint 6 (3 nov)** — Análisis completo, score ponderado y tablero. Pruebas: 123 de backend · 12 unitarias del frontend · 7 e2e.

## Objetivo del sprint

Completar los pasos 6 a 10 del análisis (pytest, coverage, Ruff, Radon y el score) y mostrar el score ponderado por categoría en Repositorios y en un tablero con su tendencia.

**Demo:** Analizar demo_repo con los 10 pasos → el score aparece en su tarjeta de Repositorios → el tablero muestra score global, categorías, tendencia y hallazgos prioritarios → cambiar pesos en Configuración y ver el score recalculado sin re-analizar.

**Criterio de aceptación:** Pruebas de backend, unitarias y e2e en verde; el score del frontend coincide con el de la API.

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

Llega en los siguientes sprints:

- Reporte de hallazgos, asistente IA (paso 11) y editor (S7)
- Compartir y exportar (S8)
- Comparativa (S9)

## Tareas del sprint

| # | Responsable | Equipo | Tarea | Archivos |
|---|---|---|---|---|
| 1 | Uriel Castorela | IA & Analizadores | Pipeline completo: pasos 6 a 10 y analizadores elegibles | pipeline.py, fake.py, jobs.py, analysis/router.py |
| 2 | Marco Espino | IA & Analizadores | Ruff y Radon, y catálogo de reglas | analyzers.py, docs/ia/catalogo-reglas.md |
| 3 | Diego Salinas | IA & Analizadores | Score ponderado por categoría y su documento | scoring.py, docs/ia/score.md |
| 4 | Carlos Jara | Backend & Plataforma | Sandbox: pytest y coverage | sandbox.py, config.py |
| 5 | Ana Cristina Luciano | Backend & Plataforma | Reportes con métricas y API del reporte | store.py, models.py, workspace.py, reports/router.py, db.py |
| 6 | Dylan Martínez | Backend & Plataforma | Tablero, lista de repos con score e historial | dashboard/router.py, views.py, schemas.py, main.py, repos/router.py |
| 7 | Evelyn Martínez | QA | Pruebas del análisis completo y datos de demostración | test_analysis.py, test_jobs.py, test_sandbox.py, seed.py |
| 8 | Luis Gabriel Manzano | QA | Pruebas del score, del tablero y de la configuración | test_scoring.py, test_modules.py, test_config_proyecto.py, test_seguridad.py |
| 9 | Karen Peña | Front-End & UX | Análisis en vivo con 10 pasos y analizadores elegibles | jobSteps.ts, JobView, AnalyzeForm, job.store, types |
| 10 | Emiliano Sánchez | Front-End & UX | Score en Repositorios | RepoCard, ReposPage, repos/api, repos/types |
| 11 | Andrea Nallely Peña Osorio | Front-End & UX | Tablero y coordinación del sprint | DashboardPage, ScoreCards, TrendChart, RecentAnalyses, routes, navigation, mocks |

## Comandos

```bash
# Backend (http://localhost:8000, docs en /docs)
cd backend
uv sync --extra dev
cp .env.example .env       # llenar GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET (ver backend/README.md)
uv run uvicorn app.main:app --reload --port 8000
uv run pytest              # 123 pruebas
uv run python -m app.seed --login <tu-usuario-de-github>   # datos de demostración (después de entrar una vez)

# Frontend (http://localhost:5173; /api y /ws van al backend)
cd frontend
npm install
npm run dev
npm run build
npm test                   # 12 pruebas unitarias
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
