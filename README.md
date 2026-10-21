# IA voy

Analizador de calidad de código **Python** para equipos. El usuario indica un repositorio Git (URL + rama);
el backend lo clona, lo analiza y genera un **reporte** con un score por categoría: seguridad, pruebas y
buenas prácticas.

> Estado: **Sprint 3** — conexión con la API de IA y clonación de repositorios.

## Demo del sprint

La IA diagnostica un archivo de un repositorio clonado:

1. Levantar el backend con `GEMINI_API_KEY` en `backend/.env` (ver [backend/README.md](backend/README.md)).
2. Levantar el frontend (`cd frontend && npm install && npm run dev`) y abrir `http://localhost:5173`.
3. Escribir la URL de un repositorio público de GitHub (y opcionalmente un archivo) → **Diagnosticar con IA**.

Sin backend, el frontend puede usar el backend simulado (MSW): crear `frontend/.env.development.local` con
`VITE_USE_MOCKS=true`.

## Organización del proyecto

| Carpeta | Contenido | Equipo |
|---|---|---|
| [backend/](backend) | API (FastAPI + SQLite): clonación, cliente de la IA y diagnóstico | Backend & Plataforma · IA & Analizadores |
| [frontend/](frontend) | React 19 + Vite + Tailwind: sistema de diseño, cliente API, mocks MSW y pantalla de diagnóstico | Front-End & UX |
| [docs/](docs) | Especificación del frontend, prompts, parsing y estabilidad del diagnóstico | Todos |
| [ia_voy_prototipo.html](ia_voy_prototipo.html) | Wireframes navegables | Front-End & UX |

| Equipo | Líder | Integrantes |
|---|---|---|
| Front-End & UX | Andrea Peña | Karen Peña, Emiliano Sánchez |
| Backend & Plataforma | Dylan Martínez | Carlos Jara, Ana Cristina Luciano |
| IA & Analizadores | Uriel Castorela | Marco Espino, Diego Salinas |
| QA (Pruebas Automatizadas) | Evelyn Martínez | Luis Gabriel Manzano |

## Entregables del Sprint 3

- Clonación real de repositorios de GitHub ([backend/app/analysis/clone.py](backend/app/analysis/clone.py)).
- Cliente de la API de IA ([backend/app/assistant/llm.py](backend/app/assistant/llm.py)) y prompts con RF, RNF y
  reglas de negocio ([backend/app/diagnostico/prompts.py](backend/app/diagnostico/prompts.py)).
- Endpoint `POST /api/diagnostico` ([backend/app/diagnostico/router.py](backend/app/diagnostico/router.py)).
- Pruebas de integración clonación ↔ IA (sin red: git y Gemini sustituidos) — 16 pruebas.
- Medición de estabilidad del diagnóstico: [docs/ia/estabilidad-diagnostico.md](docs/ia/estabilidad-diagnostico.md).
- Frontend: proyecto React + Vite, sistema de diseño (`shared/ui`), cliente API único y tipos del contrato,
  backend simulado con MSW y la pantalla de URL → resultado de la IA.

## Comandos

```bash
# Backend
cd backend
uv sync --extra dev
uv run uvicorn app.main:app --reload --port 8000
uv run pytest              # 16 pruebas

# Frontend
cd frontend
npm install
npm run dev                # http://localhost:5173 (redirige /api al backend en :8000)
npm run build
```
