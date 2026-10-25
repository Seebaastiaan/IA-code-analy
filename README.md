# IA voy

Analizador de calidad de código **Python** para equipos. El usuario indica un repositorio de GitHub (URL +
rama); el backend lo clona, lo analiza y guarda el resultado en el historial del repositorio.

> Estado: **Sprint 5 (27 oct)** — Seguridad: dependencias, Bandit y pip-audit. Pruebas: 109 de backend · 12 unitarias del frontend · 7 e2e.

## Objetivo del sprint

Llevar el análisis hasta el paso 5: instalar las dependencias del repo en el sandbox y revisar su seguridad con Bandit (código) y pip-audit (dependencias).

**Demo:** Analizar demo_repo con SANDBOX=wsl → terminal en vivo con los 5 pasos (clonar, entorno, dependencias, Bandit, pip-audit) → el análisis queda en Repositorios con sus hallazgos por severidad.

**Criterio de aceptación:** Pruebas de backend, unitarias y e2e en verde; Bandit y pip-audit corren de verdad y sus hallazgos quedan guardados en cada análisis.

## Lo que hace la app

- Login con GitHub (OAuth); el token se guarda cifrado con Fernet y nunca llega al navegador
- Nuevo análisis: elegir un repo de la cuenta de GitHub (también privados) y su rama, o escribir la URL
- Clonado real y detección de lenguajes (solo Python); terminal en vivo por WebSocket; cancelar y reintentar
- Entorno aislado (`uv venv`) en el sandbox WSL2/Docker o, sin sandbox, en el backend
- Repositorios con sus análisis guardados, archivos del clon, configuración del proyecto (`.ia_voy.toml`) y equipo
- Dependencias del repo instaladas en el sandbox; Bandit revisa el código y pip-audit las dependencias
- Cada análisis guarda sus hallazgos de Seguridad y Repositorios los muestra por severidad

Llega en los siguientes sprints:

- pytest, coverage, Ruff, Radon y el score ponderado; tablero (S6)
- Reporte de hallazgos, asistente IA y editor (S7)
- Compartir y exportar (S8)
- Comparativa (S9)

## Tareas del sprint

| # | Responsable | Equipo | Tarea | Archivos |
|---|---|---|---|---|
| 1 | Carlos Jara | Backend & Plataforma | Sandbox: instalar dependencias y correr pip-audit | sandbox.py |
| 2 | Uriel Castorela | IA & Analizadores | Orquestación de los pasos 2 a 5 | jobs.py, steps.py |
| 3 | Marco Espino | IA & Analizadores | Bandit sobre el clon | analyzers.py, models.py |
| 4 | Diego Salinas | IA & Analizadores | Hallazgos de pip-audit e instalación fallida | pipeline.py |
| 5 | Ana Cristina Luciano | Backend & Plataforma | Guardar los hallazgos y contarlos por severidad | store.py, schemas.py, views.py, repos/router.py |
| 6 | Dylan Martínez | Backend & Plataforma | Dependencias del backend y datos de demostración con hallazgos | pyproject.toml, seed.py |
| 7 | Evelyn Martínez | QA | Pruebas del sandbox y CI | test_sandbox.py, ci.yml |
| 8 | Luis Gabriel Manzano | QA | Pruebas de Bandit, pip-audit y del análisis | test_seguridad.py, test_analysis.py, test_jobs.py |
| 9 | Karen Peña | Front-End & UX | Análisis en vivo con los 5 pasos | jobSteps.ts, JobView, AnalyzeForm, steps.test.ts |
| 10 | Emiliano Sánchez | Front-End & UX | Hallazgos en Repositorios | SavedReports, RepoCard, FindingCounts, types |
| 11 | Andrea Nallely Peña Osorio | Front-End & UX | Backend simulado, e2e y coordinación del sprint | mocks/db.ts, flujos.e2e.ts, README.md |

## Comandos

```bash
# Backend (http://localhost:8000, docs en /docs)
cd backend
uv sync --extra dev
cp .env.example .env       # llenar GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET (ver backend/README.md)
uv run uvicorn app.main:app --reload --port 8000
uv run pytest              # 109 pruebas
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
