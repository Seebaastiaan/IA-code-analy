# IA voy

Analizador de calidad de código **Python** para equipos. El usuario indica un repositorio de GitHub (URL +
rama); el backend lo clona, lo analiza y guarda el resultado en el historial del repositorio.

> Estado: **Sprint 8 (17 nov)** — Compartir y exportar el reporte; reglas de negocio verificadas con pruebas. Pruebas: 235 de backend · 28 unitarias del frontend · 9 e2e.

## Objetivo del sprint

Compartir el reporte con personas fuera del equipo (enlace con contraseña y expiración) y exportarlo a JSON, HTML, Markdown y SARIF; medir la calidad del asistente con un set de evaluación.

**Demo:** Compartir el reporte con contraseña → abrir el enlace sin sesión → contraseña incorrecta y luego correcta → exportar a SARIF y HTML. Reporte → pestaña **Reglas** → una regla verificada por su prueba (`@pytest.mark.regla`) → Configuración → Reglas de negocio → validar y cargar un `reglas_negocio.toml`.

**Criterio de aceptación:** Pruebas de backend, unitarias y e2e en verde; la vista pública no muestra el código si no se permitió; una regla con una prueba que falla queda "no cumple" con la prueba como evidencia.

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
- Asistente IA (RAG con Gemini) con respuestas en streaming y fuentes archivo:línea; editor Monaco con correcciones: las de Ruff y pip-audit automáticas, las demás (Bandit, pruebas que fallan…) propuestas por la IA, siempre con diff antes de guardar
- Recomendaciones concretas por regla (qué cambiar y con qué código), sin mandar a leer la documentación
- Compartir el reporte con un enlace público (contraseña y expiración opcionales) y exportarlo a JSON, HTML, Markdown o SARIF
- Reglas de negocio del proyecto (`reglas_negocio.toml`, [ADR-003](docs/adr/ADR-003-reglas-de-negocio.md)): paso 10 del análisis con patrones y con las pruebas marcadas `@pytest.mark.regla("RN-###")` (o `test_rn###_…`), que pytest corre en el sandbox con el plugin `ia_voy_reglas`; vista **Reglas** en el reporte (regla → estado → evidencia) y pestaña **Configuración → Reglas de negocio** (plantilla, validar, cargar en la app, descargar para el repo); aún no cuentan en el score

Llega en los siguientes sprints:

- Comparativa entre análisis y respaldo del modelo del asistente (S9)
- Documentación y entrega (S10)

## Tareas del sprint

| # | Responsable | Equipo | Tarea | Archivos |
|---|---|---|---|---|
| 1 | Carlos Jara | Backend & Plataforma | Enlaces públicos del reporte | share/router.py |
| 2 | Ana Cristina Luciano | Backend & Plataforma | Tablas de enlaces y freno a la fuerza bruta | db.py |
| 3 | Diego Salinas | IA & Analizadores | Exportación del reporte (JSON, HTML, MD, SARIF) | reports/router.py |
| 4 | Uriel Castorela | IA & Analizadores | Set de evaluación del asistente | docs/ia/evaluacion.md |
| 5 | Marco Espino | IA & Analizadores | Ajustes del prompt con el set de evaluación | docs/ia/ajustes-prompt.md |
| 6 | Dylan Martínez | Backend & Plataforma | Integración y versión del backend | main.py, pyproject.toml |
| 7 | Luis Gabriel Manzano | QA | Pruebas de compartir y exportar | test_share.py, test_modules.py |
| 8 | Evelyn Martínez | QA | Flujo e2e de compartir | flujos.e2e.ts |
| 9 | Karen Peña | Front-End & UX | Modal Compartir | ShareModal, ReportHeader, ReportPage |
| 10 | Emiliano Sánchez | Front-End & UX | Vista pública del reporte | PublicReportPage, routes |
| 11 | Andrea Nallely Peña Osorio | Front-End & UX | Backend simulado de compartir y exportar; coordinación | mocks/db.ts, mocks/handlers |

## Comandos

```bash
# Backend (http://localhost:8000, docs en /docs)
cd backend
uv sync --extra dev
cp .env.example .env       # llenar GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET (ver backend/README.md)
uv run uvicorn app.main:app --reload --reload-dir app --port 8000
uv run pytest              # 235 pruebas
uv run python -m app.seed --login <tu-usuario-de-github>   # datos de demostración (después de entrar una vez)

# Frontend (http://localhost:5173; /api y /ws van al backend)
cd frontend
npm install
npm run dev
npm run build
npm test                   # 28 pruebas unitarias
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
| [docs/](docs) | Especificación y estructura del frontend, ADRs y documentación técnica; [repos de prueba](docs/repos-de-prueba.md) |
| [ia_voy_prototipo.html](ia_voy_prototipo.html) | Wireframes navegables originales |

## Equipos

| Equipo | Líder | Integrantes |
|---|---|---|
| Front-End & UX | Andrea Peña | Karen Peña, Emiliano Sánchez |
| Backend & Plataforma | Dylan Martínez | Carlos Jara, Ana Cristina Luciano |
| IA & Analizadores | Uriel Castorela | Marco Espino, Diego Salinas |
| QA (Pruebas Automatizadas) | Evelyn Martínez | Luis Gabriel Manzano |
