import { createBrowserRouter, Navigate } from 'react-router'
import { AppShell } from '@/app/layouts/AppShell'
import { SoloLayout } from '@/app/layouts/SoloLayout'
import { paths } from '@/shared/constants/paths'
import { setNavigator } from '@/shared/utils/navigation'
import { RedirectIfAuth, RequireAuth } from './guards'

/** Cada página se carga bajo demanda; `handle.title` alimenta el título del header. */
const page = (load: () => Promise<{ default: React.ComponentType }>) => async () => ({ Component: (await load()).default })

export const router = createBrowserRouter([
  {
    Component: SoloLayout,
    children: [
      {
        Component: RedirectIfAuth,
        children: [{ path: '/login', lazy: page(() => import('@/features/auth/pages/LoginPage')) }],
      },
      // Público: sirve para el login y para volver a autorizar GitHub con la sesión abierta
      { path: '/github/callback', lazy: page(() => import('@/features/auth/pages/GithubCallbackPage')) },
    ],
  },
  {
    Component: RequireAuth,
    children: [
      {
        Component: AppShell,
        children: [
          // Inicio: mientras no hay tablero, la app abre en "Nuevo análisis"
          { index: true, element: <Navigate to={paths.analyze()} replace /> },
          { path: '/dashboard', element: <Navigate to={paths.analyze()} replace /> },
          { path: '/analyze', handle: { title: 'Nuevo análisis' }, lazy: page(() => import('@/features/analysis/pages/AnalyzePage')) },
          { path: '/analyze/jobs/:jobId', handle: { title: 'Nuevo análisis' }, lazy: page(() => import('@/features/analysis/pages/AnalyzePage')) },
          {
            path: '/repos/:repoId',
            children: [{ path: 'reports/:reportId', handle: { title: 'Reporte' }, lazy: page(() => import('@/features/report/pages/ReportPage')) }],
          },
        ],
      },
    ],
  },
  { path: '*', lazy: page(() => import('@/app/NotFoundPage')) },
])

// Permite navegar desde fuera de componentes (acciones de toasts, stores)
setNavigator((to) => void router.navigate(to))
