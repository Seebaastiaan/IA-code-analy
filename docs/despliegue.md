# Despliegue con Cloudflare Tunnel

Responsable: Carlos Jara (Backend & Plataforma) · Sprint 10

IA voy corre en una máquina del equipo (backend + frontend) y se publica con **Cloudflare Tunnel**, sin abrir
puertos ni contratar un servidor. Cloudflare da una URL pública (`https://….trycloudflare.com` o un dominio propio)
que llega al Vite/servidor estático de la máquina, y éste redirige `/api` y `/ws` al backend.

```text
Navegador ──HTTPS──▶ Cloudflare ──túnel──▶ cloudflared (máquina del equipo)
                                              └─▶ frontend :5173  ──/api, /ws──▶ backend :8000
```

## 1. Requisitos en la máquina

| Herramienta | Para qué |
|---|---|
| Python 3.12 + `uv` | Backend |
| Node.js ≥ 20.19 | Frontend |
| Git | Clonar los repos analizados |
| Docker Desktop | Sandbox (`SANDBOX=docker`): obligatorio si entran personas ajenas al equipo |
| `cloudflared` | Túnel (`winget install Cloudflare.cloudflared` o https://developers.cloudflare.com/cloudflared/) |

## 2. Backend

```bash
cd backend
uv sync
cp .env.example .env
```

En `backend/.env`:

| Variable | Valor en producción |
|---|---|
| `FRONTEND_URL` | La URL pública del túnel, p. ej. `https://ia-voy.trycloudflare.com` (CORS y `redirect_uri` de GitHub) |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | De una OAuth App **de producción** (ver §4) |
| `SANDBOX` | `docker` |
| `GEMINI_API_KEY` / `GROQ_API_KEY` | Claves del asistente (Groq opcional, respaldo) |
| `SECRET_KEY` / `TOKEN_ENCRYPTION_KEY` | Fijarlas (no dejar que se generen) y respaldarlas: si cambian, las sesiones vencen y hay que volver a conectar GitHub |
| `CLONES_PATH` | Una carpeta fuera de OneDrive/Dropbox con espacio suficiente |

Arrancar con varios workers (los jobs viven en SQLite):

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
```

El backend escucha solo en `127.0.0.1`: el único acceso desde fuera es el túnel.

## 3. Frontend

Para la entrega se usa el build de producción servido por Vite (`vite preview` reutiliza el proxy de `/api` y `/ws`):

```bash
cd frontend
npm ci
npm run build
npx vite preview --host 127.0.0.1 --port 5173
```

`VITE_USE_MOCKS` debe ser `false` (valor de `.env.development` y por defecto en el build).

## 4. OAuth App de producción

GitHub → Settings → Developer settings → OAuth Apps → **New OAuth App**:

- Homepage URL: la URL pública.
- Authorization callback URL: `<URL pública>/github/callback`.

Mantener una OAuth App para desarrollo (`http://localhost:5173`) y otra para producción. Si la URL del túnel
cambia (túnel rápido), hay que actualizar la OAuth App y `FRONTEND_URL`.

## 5. Túnel

**Túnel rápido** (URL aleatoria, ideal para la demo):

```bash
cloudflared tunnel --url http://localhost:5173
```

Copia la URL `https://….trycloudflare.com` que imprime y úsala en §2 y §4.

**Túnel con nombre** (URL fija, requiere un dominio en Cloudflare):

```bash
cloudflared tunnel login
cloudflared tunnel create ia-voy
cloudflared tunnel route dns ia-voy ia-voy.<tu-dominio>
cloudflared tunnel run --url http://localhost:5173 ia-voy
```

Los enlaces públicos de los reportes (`/r/{id}`) y las invitaciones a equipos (`/join/{code}`) usan el origen
desde el que se pidieron, así que funcionan con la URL del túnel sin configurar nada más.

## 6. Verificación

| Paso | Esperado |
|---|---|
| Abrir la URL pública | Pantalla de login |
| Continuar con GitHub | Vuelve a la URL pública con la sesión iniciada |
| `<URL>/api/health` | `Sandbox Docker · Activo` y el modelo del asistente configurado |
| Analizar `seed_data/demo_repo` | Terminal en vivo (WebSocket por el túnel) y reporte con datos reales |
| Compartir un reporte y abrirlo en otra red | Vista pública sin sesión |

## 7. Operación

- **Respaldo**: `backend/data/` (base SQLite, `secrets.json`, respaldos del editor). Copiarla con el backend detenido.
- **Logs**: la terminal de uvicorn; los errores inesperados de un job quedan en el log con su id.
- **Actualizar**: `git pull`, `uv sync`, `npm ci && npm run build`, reiniciar backend y `vite preview`.
- **Apagar el acceso público**: detener `cloudflared`; la app sigue en `localhost`.
