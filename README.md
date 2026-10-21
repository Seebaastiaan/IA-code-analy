# IA voy

Analizador de calidad de código **Python** para equipos. El usuario indica un repositorio Git (URL + rama);
el backend lo clona, ejecuta los analizadores, calcula un **score ponderado** por categoría (seguridad,
pruebas y buenas prácticas) y genera un **reporte** navegable.

> Estado: **Sprint 4 (20 oct)** — Motor determinista, login con GitHub y Buenas Prácticas. Pruebas: 47 de backend · 9 unitarias del frontend.

## Objetivo del sprint

Reemplazar el diagnóstico por IA con un motor de análisis determinista, entrar con GitHub y ver el análisis en vivo.

**Demo:** Login con GitHub → URL de un repo Python → terminal en vivo con los 11 pasos → reporte con hallazgos de Ruff, Bandit y Radon y su score. pip-audit, pytest y coverage aparecen como "(simulado)" hasta el Sprint 5.

**Criterio de aceptación:** 47 pruebas de backend y 9 unitarias del frontend en verde; CI activo en cada PR.

## Lo que hace la app

- Login con GitHub (OAuth); el token se guarda cifrado con Fernet y nunca llega al navegador
- Nuevo análisis: clonado real, 11 pasos en vivo por WebSocket, Ruff + Bandit + Radon reales
- Reporte con score por categoría, hallazgos, cobertura y complejidad; solo Python (otros lenguajes se detienen con un mensaje)

Decisión de arquitectura: el código determinista detecta y puntúa; la IA solo explica y responde
([docs/adr/ADR-001-motor-determinista.md](docs/adr/ADR-001-motor-determinista.md)).

## Tareas del sprint

| # | Responsable | Equipo | Tarea | Archivos |
|---|---|---|---|---|
| 1 | Dylan Martínez | Backend & Plataforma | Login con GitHub y sesión de la app | auth.py, github/, main.py, config.py |
| 2 | Ana Cristina Luciano | Backend & Plataforma | Guardado de reportes, hallazgos y equipo personal | store.py, views.py, reports/, teams/ |
| 3 | Marco Espino | IA & Analizadores | Score por categoría | scoring.py |
| 4 | Diego Salinas | IA & Analizadores | Detección de lenguajes: solo Python | languages.py (y retira su script del Sprint 3) |
| 5 | Uriel Castorela | IA & Analizadores | Pipeline determinista (Ruff, Bandit, Radon) y ADR-001 | analyzers.py, pipeline.py, ADR-001 |
| 6 | Carlos Jara | Backend & Plataforma | Jobs de análisis y progreso en vivo | jobs.py, router.py, fake.py (y retira el prototipo) |
| 7 | Evelyn Martínez | QA | Golden repo, datos de demo y CI | ci.yml, seed.py, demo_repo, conftest.py |
| 8 | Luis Gabriel Manzano | QA | Pruebas del análisis y del score | 4 pruebas de backend y 2 unitarias |
| 9 | Emiliano Sánchez | Front-End & UX | Login con GitHub y marco de la app | auth/, AppShell, Sidebar, TopBar |
| 10 | Karen Peña | Front-End & UX | Análisis en vivo y reporte v1 | JobView, JobPill, job.store, report/ |
| 11 | Andrea Nallely Peña Osorio | Front-End & UX | Pantalla Nuevo análisis y rutas de la app | AnalyzeForm, AnalyzePage, routes, guards |

## Comandos

```bash
# Backend (http://localhost:8000, docs en /docs)
cd backend
uv sync --extra dev
cp .env.example .env       # llenar GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET (ver backend/README.md)
uv run uvicorn app.main:app --reload --port 8000
uv run pytest              # 47 pruebas
uv run python -m app.seed --login <tu-usuario-de-github>   # datos de demostración (después de entrar una vez)

# Frontend (http://localhost:5173; /api y /ws van al backend)
cd frontend
npm install
npm run dev
npm run build
npm test                   # 9 pruebas unitarias
```

Sin backend: crear `frontend/.env.development.local` con `VITE_USE_MOCKS=true` y `VITE_AUTO_LOGIN=true`
para usar el backend simulado (MSW) con la cuenta de prueba.

## Estructura

| Carpeta | Contenido |
|---|---|
| [backend/](backend) | API FastAPI + SQLite (detalle en [backend/README.md](backend/README.md)) |
| [frontend/](frontend) | React 19 + Vite + Tailwind, por módulos (`app → features → shared`) |
| [docs/](docs) | Especificación del frontend, ADRs, documentos de IA y QA |
| [ia_voy_prototipo.html](ia_voy_prototipo.html) | Wireframes navegables originales |

## Equipos

| Equipo | Líder | Integrantes |
|---|---|---|
| Front-End & UX | Andrea Peña | Karen Peña, Emiliano Sánchez |
| Backend & Plataforma | Dylan Martínez | Carlos Jara, Ana Cristina Luciano |
| IA & Analizadores | Uriel Castorela | Marco Espino, Diego Salinas |
| QA (Pruebas Automatizadas) | Evelyn Martínez | Luis Gabriel Manzano |
