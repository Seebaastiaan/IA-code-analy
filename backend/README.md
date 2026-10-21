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
│   ├── analysis/
│   │   └── clone.py     clonado real (git clone --depth 1) en CLONES_PATH
│   ├── assistant/
│   │   └── llm.py       cliente de la API de IA (Gemini por REST, respuesta en JSON con esquema)
│   ├── diagnostico/     prototipo: POST /api/diagnostico (la IA diagnostica un archivo)
│   └── analyses/
│       ├── models.py    contrato de datos del análisis (hallazgos, cobertura, complejidad)
│       └── schemas.py   modelos del contrato REST (docs/FRONTEND_SPEC.md §6)
├── scripts/
│   └── estabilidad_diagnostico.py   corre el diagnóstico N veces y compara (docs/ia/estabilidad-diagnostico.md)
└── tests/
    └── fixtures/        salidas reales de cada analizador (docs/qa/parsing.md)
```

## Claves de `.env`

| Variable | Descripción |
|---|---|
| `FRONTEND_URL` | Origen del frontend (CORS) |
| `SECRET_KEY`, `TOKEN_ENCRYPTION_KEY` | Opcionales: si están vacías se generan y se guardan en `data/secrets.json` |
| `DATABASE_PATH` | Ruta de la base SQLite (`data/ia_voy.db`) |
| `CLONES_PATH` | Carpeta de los clones (vacía = `%LOCALAPPDATA%\ia-voy\repos` o `~/.cache/ia-voy/repos`; evitar OneDrive) |
| `GEMINI_API_KEY` | Clave de la API de IA: https://aistudio.google.com/apikey (sin ella el diagnóstico responde `503`) |
| `GEMINI_MODEL` | Opcional; por defecto `gemini-3.8-flash` |

## Diagnóstico con IA (prototipo)

```bash
curl -X POST http://localhost:8000/api/diagnostico -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/equipo/api-pagos", "branch": "main", "file": "api.py"}'
```

Respuesta: `{repo, branch, commit, file, files, model, diagnostico: {resumen, score, hallazgos[]}}`.
Requiere `git` instalado en el servidor.
