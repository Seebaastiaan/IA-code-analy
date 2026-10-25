# ADR-002 · El código del repo analizado se ejecuta en un sandbox (WSL2 o Docker)

- Estado: aceptada
- Fecha: 27 de octubre de 2026 (Sprint 5)
- Responsable: Carlos Jara (Backend & Plataforma)

## Contexto

Bandit (y en el Sprint 6 Ruff y Radon) solo **lee** el código y corre en el backend. Instalar las dependencias
del repositorio y correr pip-audit (y en el Sprint 6 pytest y coverage), en cambio, **ejecuta** código del
repositorio analizado: los paquetes corren sus scripts de instalación y las pruebas importan sus módulos.
Hacerlo en el mismo proceso o máquina que la API expondría las claves del `.env` (OAuth de GitHub), la base de
datos y los clones de otros equipos.

En el Sprint 4 el sandbox ya creaba el entorno aislado (`uv venv`). Este ADR fija cómo crece en el Sprint 5.

## Decisión

Un solo script bash ([backend/app/analysis/sandbox.py](../../backend/app/analysis/sandbox.py)) corre en el entorno
que indique `SANDBOX`:

| `SANDBOX` | Cómo corre | Aislamiento | Uso |
|---|---|---|---|
| `off` | El entorno se crea en el backend (`python -m venv`, sin ejecutar nada del repo); las dependencias no se instalan y pip-audit no corre | — | Desarrollo y pruebas automatizadas |
| `wsl` | `wsl -d Ubuntu-24.04 setsid --wait bash -l sandbox.sh SRC OUT` | Del entorno de Windows (variables, procesos), **no** del disco (`/mnt/c`) | Repos propios o de confianza |
| `docker` | Contenedor desechable `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`, clon de solo lectura, 2 GB RAM, 2 CPUs, 512 procesos | Real | Repos ajenos |

El script:

1. Copia el clon a una carpeta temporal **sin** `.git`, `node_modules`, entornos, `dist`/`build` ni archivos de
   más de 5 MB (el clon que usa el editor no se toca).
2. Corre tres fases con límite de tiempo cada una y deja en `OUT` un `{fase}.code` y un `{fase}.log`:
   `venv` (`uv venv`), `install` (`uv pip install -r requirements.txt` o `-e .`) y `audit` (`pip-audit` sobre
   las dependencias instaladas, resultado en `audit.json`). En el Sprint 6 se agregan `tests`
   (`coverage run -m pytest --junitxml`) y `coverage` (`coverage json`).
3. El job espera cada `.code` para avanzar la terminal en vivo; Bandit corre en paralelo en el backend.

Reglas:

- El proceso del sandbox recibe un entorno mínimo (`PATH`, `HOME`, `TEMP`…): no hereda las claves del backend.
- Si el sandbox no está disponible (no hay `wsl.exe` o Docker no corre), el análisis **no falla**: el entorno
  se crea en el backend, pip-audit no corre y la terminal lo avisa. Si el entorno no se puede crear, el análisis
  se detiene con un error claro y se puede reintentar desde ese paso.
- Una instalación de dependencias fallida no detiene el análisis: queda como hallazgo (`DEPS`).
- Cancelar o agotar el tiempo (`SANDBOX_TIMEOUT_S`, 1200 s) mata también lo que corre dentro: en WSL la sesión
  del script (`pkill -s`), en Docker el contenedor (`docker kill`).
- El formulario "Nuevo análisis" puede apagar el sandbox para un análisis (`sandbox: false`).

## Alternativas descartadas

- **Correr en el backend con un virtualenv**: el código analizado vería el `.env` y la base de datos.
- **Solo Docker**: en las máquinas del equipo Docker Desktop no siempre está disponible; WSL2 ya está instalado.
- **Firecracker / gVisor**: más aislamiento, pero no corren en Windows y exceden el alcance del proyecto.

## Consecuencias

- Los hallazgos de Seguridad salen de datos reales (en demo_repo, pip-audit encuentra sus paquetes vulnerables).
  Pruebas y cobertura se suman en el Sprint 6 con el mismo script.
- Con `SANDBOX=wsl` el análisis tarda unos segundos más (crear el entorno e instalar dependencias).
- Antes de abrir la app a otras personas hay que usar `SANDBOX=docker` (ver `docs/qa/sandbox-docker.md`, Sprint 9).
