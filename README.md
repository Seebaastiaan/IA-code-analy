# IA voy

Analizador de calidad de código **Python** para equipos. El usuario indica un repositorio Git (URL + rama);
el backend lo clona, lo analiza y genera un **reporte** con un score por categoría: seguridad, pruebas y
buenas prácticas.

> Estado: **Sprint 2** — repositorio, API base, contratos y wireframes.

## Organización del proyecto

| Carpeta | Contenido | Equipo |
|---|---|---|
| [backend/](backend) | API (FastAPI + SQLite) | Backend & Plataforma · IA & Analizadores |
| [docs/](docs) | Especificación del frontend, diseño de prompts, esquema de parsing | Todos |
| [ia_voy_prototipo.html](ia_voy_prototipo.html) | Wireframes navegables (abrir en el navegador) | Front-End & UX |

| Equipo | Líder | Integrantes |
|---|---|---|
| Front-End & UX | Andrea Peña | Karen Peña, Emiliano Sánchez |
| Backend & Plataforma | Dylan Martínez | Carlos Jara, Ana Cristina Luciano |
| IA & Analizadores | Uriel Castorela | Marco Espino, Diego Salinas |
| QA (Pruebas Automatizadas) | Evelyn Martínez | Luis Gabriel Manzano |

## Entregables del Sprint 2

- Estructura inicial de la API: configuración por `.env`, modelo de datos inicial en SQLite y formato de
  errores `{ "error": { "code", "message" } }` ([backend/](backend)).
- Contratos de datos del análisis ([backend/app/analyses/models.py](backend/app/analyses/models.py)) y
  esquemas del contrato REST ([backend/app/analyses/schemas.py](backend/app/analyses/schemas.py)).
- Casos de uso, flujos y contrato del frontend: [docs/FRONTEND_SPEC.md](docs/FRONTEND_SPEC.md).
- Wireframes navegables: [ia_voy_prototipo.html](ia_voy_prototipo.html).
- Diseño inicial de prompts: [docs/ia/prompts.md](docs/ia/prompts.md).
- Esquema de parsing de reportes: [docs/qa/parsing.md](docs/qa/parsing.md) con ejemplos reales en
  [backend/tests/fixtures/](backend/tests/fixtures).

## Comandos

```bash
cd backend
uv sync --extra dev        # o: python -m venv .venv && pip install -e ".[dev]"
uv run uvicorn app.main:app --reload --port 8000
uv run pytest              # 4 pruebas
```

Documentación interactiva de la API: `http://localhost:8000/docs`.

## Flujo de trabajo

- Ramas `feat/<tema>` desde `develop`; un Pull Request por persona y tarea.
- Las claves (OAuth, IA) nunca se suben: `.env.example` las trae vacías.
