# IA voy — Backend

API en FastAPI que sirve al frontend (`../frontend`). El contrato está en
[`docs/FRONTEND_SPEC.md` §6](../docs/FRONTEND_SPEC.md).

**Requisitos:** Python ≥ 3.12 y Git instalado en la máquina del backend.

## Puesta en marcha

```bash
cd backend
uv sync --extra dev                 # o: python -m venv .venv && pip install -e ".[dev]"
cp .env.example .env                # y llena GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET
uv run uvicorn app.main:app --reload --port 8000
uv run pytest
```

En el frontend, `frontend/.env.development` trae `VITE_USE_MOCKS=false`: Vite redirige `/api` y `/ws` a
`http://localhost:8000` (`VITE_PROXY_TARGET`).

Datos de demostración (después de entrar una vez con GitHub):

```bash
uv run python -m app.seed --login tu-usuario-de-github
```

Analiza [seed_data/demo_repo](seed_data/demo_repo) (con problemas a propósito) con Ruff, Bandit y Radon reales
y crea 4 análisis semanales.

## Claves de `.env`

| Variable | Cómo obtenerla |
|---|---|
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | GitHub → Settings → Developer settings → **OAuth Apps** → New OAuth App. Homepage `http://localhost:5173`, callback `http://localhost:5173/github/callback` |
| `SECRET_KEY` / `TOKEN_ENCRYPTION_KEY` | Opcionales. Vacías, el backend las genera la primera vez y las guarda en `data/secrets.json` (no se sube a git) |
| `JOB_STEP_SECONDS` | Pausa entre pasos en la terminal del frontend (0.9 s) |
| `CLONES_PATH` | Carpeta de los repos clonados (por defecto `%LOCALAPPDATA%\ia-voy\repos` o `~/.cache/ia-voy/repos`). No uses OneDrive/Dropbox |
| `GEMINI_API_KEY` | Opcional. El análisis no usa IA (ADR-001) |

Las claves reales **nunca** se suben al repositorio: `.env.example` las trae vacías.

## Flujo de login

1. `POST /api/auth/github/authorize`: el backend genera un `state` (un solo uso, 10 min) y devuelve la URL de
   autorización de GitHub (`scope=repo read:user user:email`).
2. GitHub regresa al frontend en `/github/callback?code&state`; el frontend comprueba que el `state` sea el que
   inició y lo envía a `POST /api/auth/github/callback`.
3. El backend canjea el `code`, crea o actualiza el usuario (con su equipo personal), guarda el token de GitHub
   **cifrado** (Fernet) y devuelve el token de sesión de la app (HMAC con `SECRET_KEY`). El token de GitHub y
   el `client_secret` nunca llegan al navegador.

## Análisis

`POST /api/analyze` `{url, branch}` acepta solo `https://github.com/owner/repo`, crea el repo del equipo (o
reutiliza el que tenga el mismo nombre) y lanza un job que emite por `WS /ws/jobs/{id}` los mensajes
`snapshot`, `step`, `log`, `step_done`, `error` y `done`.

| # | Paso | Estado |
|---|---|---|
| 1 | `git clone --depth 1 --branch <rama>` | real (con el token del usuario si lo tiene) |
| 2-3 | Entorno y dependencias | simulado (sandbox) |
| 4 | Bandit | real |
| 5 | pip-audit | simulado (sandbox) |
| 6-7 | pytest y coverage | simulados (sandbox): sus hallazgos dicen "(simulado)" |
| 8 | Ruff | real |
| 9 | Radon | real |
| 10 | Score | real ([app/analyses/scoring.py](app/analyses/scoring.py)) |
| 11 | Índice del asistente | omitido |

**Solo Python:** al clonar se cuentan los archivos por lenguaje ([app/analysis/languages.py](app/analysis/languages.py)).
Sin `.py` el análisis se detiene con un mensaje claro; si Python es minoría se avisa en la terminal.

**Score:** `seg`/`prac` = 100 − penalización por severidad de los hallazgos abiertos; `test` = cobertura − 5 por
prueba que falla; `global` = promedio ponderado 50/30/20. Se escala por cada 1000 líneas de Python.

## Endpoints

| Módulo | Endpoints |
|---|---|
| Auth | `POST /api/auth/github/authorize`, `POST /api/auth/github/callback`, `POST /api/auth/logout`, `GET /api/auth/me` |
| Análisis | `POST /api/analyze`, `GET /api/jobs/{id}`, `WS /ws/jobs/{id}` |
| Repos | `GET /api/repos` |
| Reporte | `GET /api/report/{id}` (`id` puede ser `latest` con `?repo=`) |
| Salud | `GET /api/health` |

Errores en formato `{ "error": { "code": "...", "message": "..." } }`.

## Pruebas

```bash
uv run pytest      # GitHub y git sustituidos por clientes falsos: sin red
```
