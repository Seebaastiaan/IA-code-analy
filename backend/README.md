# IA voy · Backend

API de IA voy (FastAPI + SQLite).

## Puesta en marcha

```bash
cd backend
uv sync --extra dev
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8000
uv run pytest
```

Sin `uv`:

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"      # Windows: .venv\Scripts\pip
.venv/bin/uvicorn app.main:app --reload --port 8000
```

## Estructura

```text
backend/
├── app/
│   ├── main.py          crea la app, CORS, manejo de errores y /api/health
│   ├── config.py        configuración desde .env (pydantic-settings)
│   ├── db.py            esquema SQLite y conexión por petición
│   ├── errors.py        ApiError → { "error": { "code", "message" } }
│   └── analyses/
│       ├── models.py    contrato de datos del análisis (hallazgos, cobertura, complejidad)
│       └── schemas.py   modelos del contrato REST (docs/FRONTEND_SPEC.md §6)
└── tests/
    └── fixtures/        salidas reales de cada analizador (docs/qa/parsing.md)
```

## Claves de `.env`

| Variable | Descripción |
|---|---|
| `FRONTEND_URL` | Origen del frontend (CORS) |
| `SECRET_KEY`, `TOKEN_ENCRYPTION_KEY` | Opcionales: si están vacías se generan y se guardan en `data/secrets.json` |
| `DATABASE_PATH` | Ruta de la base SQLite (`data/ia_voy.db`) |
