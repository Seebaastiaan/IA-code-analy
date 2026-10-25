# IA voy — Estructura de carpetas del Frontend (React + Vite + Tailwind)

> Estructura del proyecto [`frontend/`](../frontend) que implementa [FRONTEND_SPEC.md](FRONTEND_SPEC.md).
> Arquitectura *feature-based*: un módulo por dominio del backend. Todas las pantallas del spec están
> implementadas y funcionan contra un backend simulado (MSW) mientras el real no exista.

## 1. Stack

| Necesidad | Librería | Notas |
|---|---|---|
| Build / dev server | **Vite 8** + `@vitejs/plugin-react` | Proxy `/api` y `/ws` al backend en desarrollo |
| UI | **React 19** + TypeScript | |
| Estilos | **Tailwind CSS 4** (`@tailwindcss/vite`) + `tailwind-merge` | Config en CSS (`@theme`), dark mode por clase; `cn()` resuelve clases en conflicto |
| Rutas | **React Router 7** (`createBrowserRouter`) | Páginas con `lazy`, guards, `handle.title` |
| Datos del servidor | **TanStack Query 5** | Caché, reintentos, mutaciones, invalidación tras cada análisis |
| Estado de cliente | **Zustand 5** | Sesión, tema, toasts, job activo, repo seleccionado, borradores del editor, chat |
| Editor de código | **Monaco** (`monaco-editor` + `@monaco-editor/react`) | Empaquetado local (sin CDN); solo se descarga al abrir el editor |
| Mocks sin backend | **MSW 2** (HTTP + WebSocket) | `VITE_USE_MOCKS=true` (activo por defecto en `.env.development`) |
| Tests | **Vitest** | `npm test` · 16 pruebas unitarias en `tests/unit` |
| Lint | oxlint | `npm run lint` |

Scripts: `npm run dev` · `npm run build` · `npm run preview` · `npm run lint` · `npm test`.

Credenciales de los mocks: `ana@equipo.dev` / `demo1234`. En desarrollo no hace falta escribirlas:
`VITE_AUTO_LOGIN=true` (en `.env.development`) inicia sesión sola y permite abrir cualquier ruta
directamente. Solo actúa junto con `VITE_USE_MOCKS=true`; con un backend real no tiene efecto.

## 2. Principios

1. **Un módulo (`features/*`) por dominio**: auth, dashboard, repos, analysis, github, report, findings,
   share, editor, assistant, compare, settings, public-report. Cada uno tiene su API, tipos, store,
   componentes y páginas, y expone lo público en `index.ts`.
2. **Solo la capa de API habla con el backend** (`shared/api` + `features/*/api`). Los componentes
   consumen hooks de TanStack Query, nunca `fetch` directo.
3. **`shared/ui`** es el design system, sin lógica de negocio.
4. **Las dependencias van en una dirección:** `app → features → shared`. `shared` nunca importa de
   `app` ni de `features`. Entre módulos se importa por `index.ts` o por un archivo concreto
   (p. ej. `editor/hooks/useApplyFix`) para no crear ciclos.
5. **Datos del servidor en TanStack Query; estado de UI en Zustand o en query params** (filtros, tab,
   archivo abierto, hallazgo abierto, modal de compartir) para que todo sea enlazable.
6. **Los tipos de `features/*/types.ts` son el contrato con el backend.** El mock los usa tal cual,
   así que si el backend real respeta esos tipos, basta con apagar `VITE_USE_MOCKS`.

## 3. Árbol

```text
frontend/
├── index.html                 fuentes, tema aplicado antes del primer pintado
├── vite.config.ts             plugins, alias @ → src, proxy /api y /ws
├── tsconfig.app.json          paths { "@/*": ["./src/*"] }
├── .env.example               VITE_API_URL, VITE_WS_URL, VITE_PROXY_TARGET, VITE_USE_MOCKS
├── .env.development           VITE_USE_MOCKS=true
├── public/
│   ├── favicon.svg
│   └── mockServiceWorker.js   generado por `msw init`
├── tests/unit/                patches · job (reductor WS) · score/tone/toml
│
└── src/
    ├── main.tsx               arranca MSW (si aplica) + Providers + RouterProvider
    ├── vite-env.d.ts
    ├── styles/globals.css     Tailwind, @theme (brand, fuentes, animaciones), tok-*, marcas de Monaco
    │
    ├── app/
    │   ├── providers.tsx      QueryClientProvider, configureHttp (token + 401), Toaster
    │   ├── NotFoundPage.tsx
    │   ├── router/
    │   │   ├── routes.tsx     tabla de rutas (§4) + registro del navegador global
    │   │   └── guards.tsx     RequireAuth, RedirectIfAuth
    │   └── layouts/
    │       ├── AppShell.tsx   Sidebar + TopBar + <Outlet/> con Suspense
    │       ├── SoloLayout.tsx login y vista pública
    │       ├── Sidebar.tsx    navegación, badge de altas abiertas, estado de servicios
    │       ├── TopBar.tsx     título, búsqueda global, JobPill, tema, usuario
    │       ├── UserMenu.tsx · Toaster.tsx
    │       └── navigation.ts  grupos y enlaces del sidebar
    │
    ├── features/
    │   ├── auth/              login con GitHub (LoginForm, useGithubLogin, GithubCallbackPage), sesión, LoginHero
    │   ├── dashboard/
    │   │   ├── api/dashboard.api.ts       GET /dashboard?repo=
    │   │   ├── components/ScoreCards.tsx  GlobalScoreCard, CategoryKpiCard
    │   │   ├── components/TrendChart.tsx  SVG con series ocultables
    │   │   ├── components/RecentAnalyses.tsx
    │   │   └── pages/DashboardPage.tsx
    │   ├── repos/
    │   │   ├── api/repos.api.ts           lista (con sondeo mientras hay análisis), árbol, re-análisis
    │   │   ├── hooks/useReanalyze.ts
    │   │   ├── store/selectedRepo.store.ts  repo activo (sidebar, búsqueda global)
    │   │   ├── components/RepoCard.tsx
    │   │   └── pages/ReposPage.tsx
    │   ├── analysis/
    │   │   ├── api/analysis.api.ts        POST /analyze, GET/DELETE /jobs/{id}, retry
    │   │   ├── store/job.store.ts         WebSocket del job + reduceJob + avisos al terminar/fallar
    │   │   ├── constants/jobSteps.ts      11 pasos, analizadores, "qué va a pasar"
    │   │   ├── components/AnalyzeForm.tsx · JobView.tsx (pasos + terminal en vivo) · JobPill.tsx
    │   │   └── pages/AnalyzePage.tsx      formulario ↔ progreso según /analyze/jobs/:jobId
    │   ├── github/
    │   │   ├── api/github.api.ts          estado del token, repos y ramas de la cuenta
    │   │   └── components/GithubRepoPicker.tsx  buscar repo de GitHub (en Nuevo análisis)
    │   ├── report/
    │   │   ├── api/report.api.ts          GET /report/{id|latest}?repo=, exportReport()
    │   │   ├── hooks/useReportFilters.ts  tab, q, sev, cat en la URL
    │   │   ├── components/ReportHeader.tsx · ReportTabs.tsx (Hallazgos, Cobertura, Complejidad)
    │   │   └── pages/ReportPage.tsx       + FindingDrawer (?finding=) + ShareModal (?share=1)
    │   ├── findings/
    │   │   ├── components/FindingDrawer.tsx  código, por qué, cómo, acciones
    │   │   ├── hooks/useFindingParam.ts      ?finding=<id>
    │   │   └── hooks/useIgnoreRule.ts        agrega la regla a la config
    │   ├── share/
    │   │   ├── api/share.api.ts
    │   │   └── components/ShareModal.tsx     contraseña, expiración, código, exportar, ver como invitado
    │   ├── editor/
    │   │   ├── api/file.api.ts               GET/PUT /file, POST /fix
    │   │   ├── monaco.ts                     Monaco local + worker
    │   │   ├── store/editor.store.ts         borradores y fixes pendientes por archivo
    │   │   ├── utils/patches.ts              applyPatches (ubica la línea aunque se haya movido)
    │   │   ├── hooks/useApplyFix.ts          pide parches → borrador → abre el diff
    │   │   ├── hooks/useSaveFile.tsx         guarda → re-análisis → toast "score X → Y"
    │   │   ├── components/CodeEditor.tsx     Editor con marcas de hallazgos + DiffEditor
    │   │   ├── components/FileTree.tsx       árbol (desktop) y selector (móvil)
    │   │   └── pages/EditorPage.tsx          toolbar, lista de hallazgos del archivo
    │   ├── assistant/
    │   │   ├── api/chat.api.ts               POST /chat, GET /repos/{id}/index
    │   │   ├── store/chat.store.ts           conversación por repo
    │   │   ├── components/ChatMessageItem.tsx  fuentes → editor, acción → fix
    │   │   └── pages/AssistantPage.tsx       ?q= se envía automáticamente una vez
    │   ├── compare/                          GET /repos/{id}/analyses, POST /diff, ComparePage
    │   ├── settings/
    │   │   ├── api/config.api.ts             config + health
    │   │   ├── utils/toToml.ts
    │   │   ├── components/SettingsForm.tsx   pesos, umbrales, reglas, rutas, servicios, TOML
    │   │   └── pages/SettingsPage.tsx
    │   └── public-report/                    GET /public/r/{id}, unlock; 401 → contraseña, 404, 410
    │
    ├── shared/
    │   ├── api/
    │   │   ├── http.ts         request, http.get|post|put|delete, download(), rutas anónimas
    │   │   ├── ws.ts           openSocket() JSON con reconexión exponencial
    │   │   ├── endpoints.ts    EP: todas las rutas del spec §6
    │   │   ├── queryClient.ts  cliente único (lo usan también los stores)
    │   │   ├── invalidate.ts   invalidateAnalysis(): refresca todo lo que depende de un análisis
    │   │   └── errors.ts       ApiError { status, code, message }
    │   ├── ui/                 Button, Card, Field, Toggle, Chip(s), Score, Overlay (Drawer/Modal),
    │   │                       Tabs/SegmentedControl, ChipList, CodeSnippet, MiniMarkdown, States
    │   │                       (Skeleton, PageLoader, ErrorState), EmptyState, Toast, Icon,
    │   │                       ThemeToggle, PageHeader, styles.ts
    │   ├── hooks/              useToast (+ toast()), useTheme
    │   ├── constants/          paths, categories, severities, tones, grades
    │   ├── utils/              cn, score, format, highlight, navigation (navigateTo fuera de React)
    │   └── types/common.ts     Category, Severity, RepoStatus, Weights, Scores, Thresholds
    │
    └── mocks/                  backend simulado (se reinicia al recargar la página)
        ├── browser.ts
        ├── db.ts               repos, reportes, score ponderado, re-análisis al guardar, jobs, shares
        ├── handlers/index.ts   todos los endpoints REST + WS /ws/jobs/:jobId
        └── fixtures/           código fuente, hallazgos + fixes, respuestas del chat, usuario, health
```

## 4. Rutas

| URL | Layout | Guard | Página |
|---|---|---|---|
| `/login` | Solo | RedirectIfAuth | `auth/pages/LoginPage` |
| `/` | — | RequireAuth | → `/dashboard` |
| `/dashboard` | AppShell | RequireAuth | `dashboard/pages/DashboardPage` |
| `/analyze` | AppShell | RequireAuth | `analysis/pages/AnalyzePage` (formulario) · `?url=&branch=` para precargar |
| `/analyze/jobs/:jobId` | AppShell | RequireAuth | `analysis/pages/AnalyzePage` (progreso en vivo) |
| `/repos` | AppShell | RequireAuth | `repos/pages/ReposPage` |
| `/repos/:repoId/reports/:reportId` | AppShell | RequireAuth | `report/pages/ReportPage` · `?tab=&q=&sev=&cat=&finding=&share=1` |
| `/repos/:repoId/editor` | AppShell | RequireAuth | `editor/pages/EditorPage` · `?file=&line=&diff=1&finding=` |
| `/repos/:repoId/assistant` | AppShell | RequireAuth | `assistant/pages/AssistantPage` · `?q=` |
| `/repos/:repoId/compare` | AppShell | RequireAuth | `compare/pages/ComparePage` |
| `/repos/:repoId/settings` | AppShell | RequireAuth | `settings/pages/SettingsPage` |
| `/r/:shareId` | Solo | público | `public-report/pages/PublicReportPage` |
| `*` | — | — | `app/NotFoundPage` |

- `reportId = latest` le pide al backend el último análisis del repo (el sidebar enlaza así).
- Sin repo seleccionado, los enlaces de Reporte/Editor/Asistente/Comparativa/Configuración llevan a
  `/repos`.

## 5. Módulo ↔ endpoints

| Módulo | Endpoints |
|---|---|
| `auth` | `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` |
| `dashboard` | `GET /api/dashboard?repo=` |
| `repos` | `GET /api/repos`, `POST /api/repos/{id}/analyze`, `GET /api/repos/{id}/tree` |
| `analysis` | `POST /api/analyze`, `WS /ws/jobs/{id}`, `GET /api/jobs/{id}`, `DELETE /api/jobs/{id}`, `POST /api/jobs/{id}/retry` |
| `report` | `GET /api/report/{id}?repo=` (`id` puede ser `latest`), `GET /api/report/{id}/export?format=` |
| `findings` / `editor` | `POST /api/fix`, `GET /api/file?repo=&path=`, `PUT /api/file` |
| `share` | `POST /api/report/{id}/share` |
| `assistant` | `POST /api/chat`, `GET /api/repos/{id}/index` |
| `compare` | `GET /api/repos/{id}/analyses`, `POST /api/diff` |
| `settings` | `GET /api/projects/{id}/config`, `PUT /api/projects/{id}/config`, `GET /api/health` |
| `public-report` | `GET /api/public/r/{id}?token=`, `POST /api/public/r/{id}/unlock` |

Todas las rutas están centralizadas en `shared/api/endpoints.ts` (`EP`). Los cuerpos y respuestas
están tipados en `features/*/types.ts`; el WebSocket del job envía primero un `snapshot` y después
`step`, `log`, `step_done`, `error` o `done` (`features/analysis/types.ts`).

## 6. Convenciones

- **Archivos:** componentes y páginas `PascalCase.tsx` (las páginas con `export default` para `lazy`),
  hooks `useXxx.ts` (`.tsx` si devuelven JSX), stores `xxx.store.ts`, APIs `xxx.api.ts`.
- **Import con alias:** `@/shared/ui`, `@/features/auth`, etc.
- **Clases reutilizables** en `shared/ui/styles.ts` (no en archivos de componentes, por Fast Refresh).
  Para sobrescribir clases de un componente, pasar `className`: `cn()` (tailwind-merge) resuelve el conflicto.
- **Consultas:** claves como arrays con la raíz del recurso primero (`['report', repoId, reportId]`).
  Tras cualquier cambio que afecte al análisis, llamar `invalidateAnalysis(queryClient)`.
- **Toasts** desde cualquier lugar con `toast(msg, { tone, action, ms })`; para navegar desde una
  acción de toast o un store, `navigateTo(path)`.
- **Variables de entorno:** `VITE_API_URL` y `VITE_WS_URL` vacías = mismo origen (proxy de Vite en
  desarrollo, túnel en producción). `VITE_PROXY_TARGET` apunta al backend local.
- **Mocks:** cada endpoint nuevo agrega su handler en `src/mocks/handlers` y su lógica en `mocks/db.ts`.

## 7. Pendientes conocidos

- **Streaming del chat (SSE):** hoy `POST /api/chat` devuelve la respuesta completa; el punto de cambio
  está marcado con `TODO(backend)` en `assistant/api/chat.api.ts`.
- **Marcas del editor tras un fix con borrado/inserción de líneas:** las marcas de los demás hallazgos
  del mismo archivo usan la línea original hasta guardar (al guardar, el re-análisis las recalcula).
- **Vista pública en el mock:** los enlaces viven en memoria; abrir `/r/:id` en otra pestaña o recargar
  da "no existe". Con el backend real no aplica.
- **Pruebas de componentes y e2e:** solo hay pruebas unitarias de la lógica; faltan Testing Library y
  los 5 journeys del spec en e2e.
