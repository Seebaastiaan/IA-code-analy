# IA voy — Backend

API en FastAPI que sirve al frontend (`../frontend`). El contrato está en
[`docs/FRONTEND_SPEC.md` §6](../docs/FRONTEND_SPEC.md).

Implementado hasta ahora:

- `/api/auth/*`: **inicio de sesión con GitHub** (la cuenta de GitHub es la cuenta de la app).
- `/api/github/*`: repos y ramas de la cuenta de GitHub del usuario.
- `/api/analyze`, `/api/jobs/*`, `WS /ws/jobs/{id}`: el **paso 1 clona de verdad** el repo de GitHub
  (públicos sin token, privados con el token del usuario). Después corren **Ruff, Bandit y Radon** sobre el
  clon y, en el **sandbox** (WSL2 o Docker, `SANDBOX`), el entorno `uv`, las dependencias, **pip-audit,
  pytest y coverage**. Con `SANDBOX=off` esos tres se simulan.
- **Tablero** (`app/dashboard`): `/api/dashboard`, `/api/repos`, `/api/repos/{id}/history`.
- **Reportes** (`app/reports`): `/api/report/{id}` y `/api/report/{id}/export?format=json|md|html|sarif`.
- **Editor** (`app/editor`): `/api/repos/{id}/tree`, `/api/file` (leer y guardar con re-análisis), `/api/fix`.
- **Asistente IA** (`app/assistant`): `POST /api/chat/stream` (respuesta por SSE mientras se genera),
  `POST /api/chat` y `GET /api/repos/{id}/index` (RAG sobre el código con Gemini).
- **Configuración** (`app/projects`): `GET` y `PUT /api/projects/{id}/config` (pesos, umbrales, reglas
  ignoradas, rutas excluidas) y `.ia_voy.toml`.
- **Comparativa** (`app/compare`): `GET /api/repos/{id}/analyses` y `POST /api/diff` (nuevos y resueltos entre
  dos análisis del mismo repo; los hallazgos se reconocen por herramienta, regla, archivo y texto de la línea).
- **Equipos** (`app/teams`): `/api/team`, invitaciones, unirse, salir, quitar y ceder (ver [Equipos](#equipos)).
- **Compartir** (`app/share`): `POST /api/report/{id}/share` y la vista pública sin sesión
  `GET /api/public/r/{id}` + `POST /api/public/r/{id}/unlock` (contraseña opcional, expiración).
- `/api/health`.

**Requisitos:** Git instalado en la máquina del backend; para el sandbox, WSL2 con `uv` (README raíz §2.1)
o Docker Desktop corriendo.

## Puesta en marcha

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
copy .env.example .env   # y llena GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Con `uv`: `uv sync --extra dev` y `uv run uvicorn app.main:app --reload --port 8000`.

En el frontend, `frontend/.env.development` con `VITE_USE_MOCKS=false`: Vite redirige `/api` y `/ws` a
`http://localhost:8000` (`VITE_PROXY_TARGET`).

## Claves de `.env`

| Variable | Cómo obtenerla |
|---|---|
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | GitHub → Settings → Developer settings → **OAuth Apps** → New OAuth App |
| `SECRET_KEY` / `TOKEN_ENCRYPTION_KEY` | Opcionales. Vacías, el backend las genera la primera vez y las guarda en `data/secrets.json` (no se sube a git). Si ese archivo se borra, las sesiones vencen y hay que volver a iniciar sesión. |
| `JOB_STEP_SECONDS` | Pausa de los pasos que no esperan al sandbox en la terminal del frontend (por defecto 0.9 s). |
| `SANDBOX` | Dónde corren pytest, coverage y pip-audit: `off` (simulados, por defecto en código), `wsl` o `docker`. Ver [Sandbox](#sandbox). |
| `SANDBOX_WSL_DISTRO` / `SANDBOX_DOCKER_IMAGE` / `SANDBOX_TIMEOUT_S` | Opcionales. Por defecto `Ubuntu-24.04`, `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` y 1200 s por análisis. |
| `GEMINI_API_KEY` | Asistente IA (respuestas y embeddings): https://aistudio.google.com/apikey. Sin ella el asistente responde `503 llm_not_configured`. |
| `GEMINI_MODEL` / `GEMINI_FALLBACK_MODELS` | Opcionales. Por defecto `gemini-3.8-flash` y, si responde 429/503, `gemini-3.5-flash,gemini-3.1-flash-lite`. |
| `GROQ_API_KEY` | Opcional. Último respaldo (Llama 3.3), independiente de Google: https://console.groq.com/keys |
| `CLONES_PATH` | Carpeta de los repos clonados (por defecto `%LOCALAPPDATA%\ia-voy\repos`). No uses una carpeta de OneDrive/Dropbox. |

Datos de la OAuth App en desarrollo:

- **Homepage URL:** `http://localhost:5173`
- **Authorization callback URL:** `http://localhost:5173/github/callback`

Para que otras personas entren, publica la app con una URL pública y usa esa URL en `FRONTEND_URL` y en la
OAuth App (lo más limpio: una OAuth App para desarrollo y otra para producción).

## Flujo de login

1. El frontend pide `POST /api/auth/github/authorize`; el backend genera un `state` (un solo uso, 10 min)
   y devuelve la URL de autorización de GitHub (`scope=repo read:user user:email`).
2. GitHub regresa al frontend en `/github/callback?code&state`; el frontend comprueba que el `state` sea el
   que inició y lo envía a `POST /api/auth/github/callback`.
3. El backend canjea el `code`, crea o actualiza el usuario, guarda el token de GitHub **cifrado** (Fernet)
   en SQLite y devuelve el token de sesión de la app. El token de GitHub y el `client_secret` nunca llegan
   al navegador.

Si el usuario revoca el acceso en GitHub, `/api/github/*` responde `409 github_not_connected` (no `401`,
que el frontend interpreta como sesión vencida) y el frontend ofrece volver a autorizar.

## Análisis

`POST /api/analyze` `{url, branch, analyzers, sandbox, index}` acepta solo URLs `https://github.com/owner/repo`,
crea el repo (o reutiliza el del equipo con el mismo `owner/repo`) y lanza un job que emite por
`WS /ws/jobs/{id}` los mensajes `snapshot`, `step`, `log`, `step_done`, `error` y `done`.

**Analizadores elegidos:** `analyzers` vacío = todos. Si se eligen, al menos uno por categoría (si no,
`422 missing_analyzers`). Los no elegidos no corren: su paso dice "omitido (no seleccionado)" y no aportan
hallazgos. Sin coverage, la cobertura queda "no medida" (`summary.coverage_total = null`) y el score de
pruebas solo descuenta las que fallan. El reporte guarda la lista (`analyzers`) y re-analizar la repite.
`index: false` omite el paso 11 (índice del asistente).

**Jobs persistentes** (tabla `jobs`, [app/analysis/jobs.py](app/analysis/jobs.py)): el proceso que corre un
job guarda su estado con cada evento y renueva un latido cada 5 s.
- `GET /api/jobs/{id}` y el WebSocket funcionan desde cualquier worker: el que no corre el job lee su fila
  (el WebSocket cada 0.5 s).
- Un job `running` sin latido por más de 30 s se interrumpió (reinicio del servidor): se muestra como error
  "El análisis se interrumpió" y `retry` lo vuelve a correr desde el clonado.
- Cancelar desde otro worker marca el job; el que lo corre lo detiene en su siguiente latido.

**Paso 1, real:** `git clone --depth 1 --branch <rama>` en `CLONES_PATH/{repo_id}` (por defecto
`%LOCALAPPDATA%\ia-voy\repos`, fuera del proyecto: dentro de OneDrive la sincronización bloquea los
archivos recién clonados). Se reemplaza en cada análisis; un fallo conserva el clon anterior. Cualquier
error inesperado termina el job en `error` (nunca queda colgado en "running"). El token de GitHub viaja como cabecera HTTP en variables de
entorno de git: no queda en `.git/config` ni en la línea de comandos. Sin Git Credential Manager ni
prompts, con `core.symlinks=false` y límite de 180 s. Si falla (rama o repo inexistente, sin acceso), el
job termina en `error` con un mensaje claro y se puede reintentar.

**Pasos 2-10** ([app/analysis/pipeline.py](app/analysis/pipeline.py)):
- **En el backend:** Ruff y Bandit (hallazgos, una ejecución por repo) y Radon (complejidad). Solo leen el
  código, así que no necesitan sandbox. Ruff usa la configuración del repo si tiene; si no, `--isolated`.
- **En el sandbox:** entorno, dependencias, pip-audit, pytest y coverage (ejecutan el código del repo).
  Corren en paralelo con lo anterior y la terminal avanza con cada fase. Sin sandbox se simulan: sus
  números salen de la semilla del job y sus hallazgos dicen "(simulado)".

### Sandbox

[app/analysis/sandbox.py](app/analysis/sandbox.py) escribe un script bash y lo corre en WSL2
(`wsl -d Ubuntu-24.04 setsid --wait bash -l`) o en un contenedor Docker desechable. El script copia el clon a
una carpeta temporal (el clon del editor no se toca) **sin** `.git`, `node_modules`, entornos virtuales,
`dist`/`build` ni archivos de más de 5 MB (un repo de 338 MB con `node_modules` subido tardaba más de 20 min en
copiarse; ahora segundos). Corre, con límite de tiempo por fase:

| Fase | Comando | Hallazgos |
|---|---|---|
| venv | copia + `uv venv .venv --python 3.12` (5 min) | si falla, el sandbox no sirve y se simula (aviso en la terminal) |
| install | `uv pip install -r requirements.txt` (o `-e .` con `pyproject.toml`), más las dependencias de pruebas si el proyecto las declara: `requirements-dev.txt`, `requirements/test.txt`… y los grupos/extras `test`, `tests`, `testing`, `dev` de `pyproject.toml` | `DEPS` (alta) si no se pudo instalar lo principal |
| audit | `pip-audit --path .venv/…/site-packages -f json` (solo dependencias del proyecto) | uno por paquete vulnerable, en su línea de `requirements.txt` |
| tests | `coverage run -m pytest -q --maxfail=50 --junitxml …` | `FAIL` / `ERROR` por prueba, con su archivo y línea |
| coverage | `coverage json` | `COV` por archivo bajo la cobertura mínima |

- **WSL2:** aísla del entorno de Windows (el proceso no hereda las claves del `.env`) pero **no del disco**:
  el código analizado puede leer `/mnt/c`. Úsalo con repos propios o de confianza.
- **Docker:** clon montado de solo lectura, 2 GB de RAM, 2 CPUs y 512 procesos. Aislamiento real: úsalo
  con repos ajenos. Necesita Docker Desktop corriendo; si no, se simula con un aviso.
- En ambos casos hay red (para instalar dependencias), también mientras corren las pruebas.
- El formulario "Nuevo análisis" puede apagar el sandbox para un análisis (`sandbox: false`).
- Detener el sandbox (cancelar, tiempo agotado) mata también lo que corre dentro: en WSL la sesión del script
  (`pkill -s`), en Docker el contenedor (`docker kill`). Matar solo `wsl.exe` dejaba las pruebas vivas.
- La cobertura no cuenta pruebas ni archivos de herramientas (`setup.py`, `noxfile.py`, `conftest.py`,
  `manage.py`, `docs/`…).

### Solo Python

Al clonar se cuentan los archivos por lenguaje ([app/analysis/languages.py](app/analysis/languages.py)),
sin `node_modules`, entornos ni carpetas ocultas:
- **Sin archivos `.py`:** el análisis se detiene con "El repositorio no tiene código Python" y la lista de
  lenguajes que sí tiene.
- **Python en minoría** (menos de la mitad de los archivos de código, sin contar HTML, CSS, SQL ni scripts):
  aviso en la terminal. El reporte incluye `languages` y el frontend avisa qué no se analizó.

Al terminar, el job llama a `AnalysisStore.save_report` ([app/analyses/store.py](app/analyses/store.py)),
que guarda el reporte con sus hallazgos (tabla `findings`, con un fragmento de ±2 líneas de código).
Cada equipo ve solo sus repos.

## Equipos

[app/teams](app/teams): cada usuario pertenece a un equipo (tabla `team_members`); el primer login crea uno
propio ("Equipo de Ana"). Repos, reportes, configuración, jobs, editor e índice del asistente se filtran por
el equipo del usuario (lo de otro equipo responde `404`).

| Endpoint | Quién | Qué hace |
|---|---|---|
| `GET /api/team` | todos | Equipo, mi rol, miembros y número de repos |
| `PATCH /api/team` `{name}` | dueño | Renombrar |
| `POST /api/team/invites` | dueño | Enlace `/join/{code}` (7 días, varias personas) |
| `GET /api/team/invites/{code}` | todos | Vista previa: equipo, miembros, repos propios que se descartarían |
| `POST /api/team/join` `{code}` | todos | Unirse (`410` si la invitación venció) |
| `DELETE /api/team/members/{id}` | dueño | Quitar a alguien: vuelve a un equipo propio vacío |
| `DELETE /api/team/members/me` | miembro | Salir (el dueño debe ceder antes: `409 owner_must_transfer`) |
| `POST /api/team/members/{id}/owner` | dueño | Ceder el equipo |

Al unirse, si quien llega era el único miembro de su equipo, sus repos pasan al equipo nuevo (los que ya
existen allí con el mismo nombre se descartan) y su equipo anterior se borra. Si tenía más miembros, los
repos se quedan con ellos.

Las bases de datos anteriores a los equipos se migran solas al abrirlas: cada usuario recibe su equipo y la
tabla `repos` se reconstruye con `team_id` (sin perder reportes).

## Tablero, reportes y editor

Leen las tablas `repos`, `reports`, `findings` y `project_config` ([app/analyses/](app/analyses)).

**Score** ([scoring.py](app/analyses/scoring.py)): se calcula al leer con los hallazgos abiertos y no
ignorados. `seg`/`prac` = 100 − penalización por severidad; `test` = cobertura − 5 por prueba que
falla; `global` = promedio ponderado (50/30/20 por defecto). En proyectos de más de 1000 líneas de Python la
penalización se escala por cada 1000 líneas (si no, cualquier proyecto grande quedaba en 0: `requests` daba
24.9 y ahora 91.1). Bandit no revisa los archivos de prueba. Resolver en el editor o ignorar una regla
se refleja sin re-analizar. Los reportes anteriores a esta versión (columna `coverage_total = -1`)
conservan los `seg/test/prac` que se guardaron.

**Editor:**
- Árbol con los archivos de texto del clon (`.py`, `requirements.txt`, `README.md`…) y sus hallazgos
  abiertos. Nada fuera del clon ni oculto (`.git`, `.env`): `400 invalid_path`. Máx. 1 MB.
- `PUT /api/file` respalda la versión anterior en `data/backups/{repo}/{fecha}/{ruta}` y re-analiza el
  archivo con Ruff y Bandit: resuelve lo que desapareció, mueve lo que cambió de línea y agrega lo
  nuevo. Responde `{resolved_ids, new_ids, score_before, score_after}`.
- `POST /api/fix` devuelve parches con las correcciones "safe" de Ruff, ubicando cada hallazgo por regla
  y texto de su línea. Bandit no tiene correcciones automáticas.

**Datos de demostración** (sin analizar un repo de GitHub): entra una vez con GitHub y luego

```powershell
.\.venv\Scripts\python.exe -m app.seed --login tu-usuario-de-github
```

Analiza [seed_data/demo_repo](seed_data/demo_repo) (con problemas a propósito) con Ruff, Bandit y Radon
reales y crea 4 análisis semanales para que la tendencia tenga historia.

## Asistente IA

**Índice** ([app/assistant/index.py](app/assistant/index.py)): el código del clon se parte con el `ast` de
Python (una función o clase por fragmento; el resto de archivos de texto en bloques de 60 líneas) y cada
fragmento se guarda en SQLite (`code_chunks`) con su embedding de `gemini-embedding-001` (768 dimensiones,
normalizado). Se indexa en el paso 10 del análisis y, si falta, al abrir el asistente. Antes de cada
pregunta se re-fragmenta (local, rápido) y solo se piden embeddings de lo nuevo o cambiado (por hash): lo
guardado en el editor se refleja sin re-indexar todo.

**`POST /api/chat`** `{repo_id, message, history?}` → `{content, sources, action?, model}`:
1. Busca los 6 fragmentos más parecidos a la pregunta (similitud coseno con numpy).
2. Arma el contexto: resumen del reporte y sus hallazgos abiertos (sin reglas ignoradas), el hallazgo
   mencionado en la pregunta (`regla` y `archivo:línea`) con ±12 líneas de código, y los fragmentos.
3. Pide a Gemini una respuesta JSON con esquema (`answer`, `sources`, `finding_id`).
4. Valida: solo quedan las fuentes que estaban en el contexto (nada de `archivo:línea` inventados) y la
   acción solo se ofrece si el hallazgo está abierto y tiene corrección automática.

**`POST /api/chat/stream`** hace lo mismo pero responde con Server-Sent Events: `delta` (`{text}`) con cada
trozo del campo `answer` mientras Gemini lo genera (`streamGenerateContent`), y al final `done` (la misma
respuesta que `/api/chat`, con las fuentes ya validadas) o `error` (`{code, message}`). Es lo que usa el
frontend. Groq no hace streaming: su respuesta llega en un solo `delta`.

Si el modelo responde 429/503 se reintenta una vez y se pasa a `GEMINI_FALLBACK_MODELS` y luego a Groq
(con streaming, solo si todavía no se mostró texto).
Errores: `503 llm_rate_limited`, `llm_busy`, `llm_unavailable`, `llm_not_configured`. Si los embeddings
fallan, responde igual con el reporte (sin fragmentos). El código del repo se envía a Google para
responder; el prompt trata ese código como datos, no como instrucciones.

## Configuración del proyecto

`GET`/`PUT /api/projects/{id}/config` (el id es el del repo) → `{weights, thresholds, ignored, excluded}`.
Al guardar se valida (pesos y umbrales de 0 a 100, al menos un peso > 0, rutas relativas sin `..`) y se
normaliza (sin duplicados, `\` → `/`, sin `./` inicial); un error responde `422 invalid_config`.

- **Al instante**, sin re-analizar: pesos, umbral de score, reglas ignoradas y rutas excluidas (sus
  hallazgos salen del reporte, del score y del árbol del editor).
- **En el siguiente análisis:** la cobertura mínima (genera los hallazgos `COV`) y las rutas excluidas en
  los analizadores.
- **`.ia_voy.toml`:** al guardar se escribe en la raíz del clon. Si un repo trae su propio `.ia_voy.toml`,
  se adopta en su primer análisis; después manda lo guardado desde la pantalla Configuración.

## Compartir

`POST /api/report/{id}/share` `{password?, expires_days: 0|1|7|30, include_code}` → `{share_id, url, expires_at}`.
El enlace (`/r/{share_id}`, tabla `shares`) usa el origen desde el que se pidió (localhost o el túnel público).

- `GET /api/public/r/{share_id}` (sin sesión): score y hallazgos **abiertos de severidad alta y media**, con la
  configuración actual del proyecto. Los fragmentos de código solo si se pidió `include_code`.
  `404` si no existe, `410` si expiró, `401 password_required` si tiene contraseña.
- `POST /api/public/r/{share_id}/unlock` `{password}` → `{token}`: token firmado (HMAC, 12 h) que el frontend
  manda como `?token=`. La contraseña se guarda con scrypt. Tras 10 intentos fallidos en 15 min responde `429`.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Las pruebas sustituyen a GitHub por un cliente falso: no hacen llamadas de red.

## Limitaciones conocidas

- Jobs, `state` de OAuth e intentos de contraseña viven en SQLite, así que se puede correr con varios
  workers. Un análisis interrumpido por un reinicio se reintenta desde el clonado (el resultado parcial no se
  guarda). Para muchos usuarios a la vez conviene PostgreSQL en lugar de SQLite.
- Un usuario pertenece a un solo equipo a la vez.
- El estado del túnel de Cloudflare en `/api/health` es fijo hasta conectar el túnel.
- `/api/github/repos` trae los 100 repos con actividad más reciente; la búsqueda filtra sobre ellos.
- Los mensajes de Ruff y Bandit llegan en inglés; el asistente IA podrá explicarlos en español.
- El WebSocket del job no lleva token (el navegador no puede enviar `Authorization`): el id aleatorio del
  job funciona como credencial de lectura del progreso.
