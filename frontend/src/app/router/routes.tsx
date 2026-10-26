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
      { path: '/r/:shareId', lazy: page(() => import('@/features/public-report/pages/PublicReportPage')) },
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
          { index: true, element: <Navigate to={paths.dashboard()} replace /> },
          { path: '/dashboard', handle: { title: 'Tablero' }, lazy: page(() => import('@/features/dashboard/pages/DashboardPage')) },
          { path: '/analyze', handle: { title: 'Nuevo análisis' }, lazy: page(() => import('@/features/analysis/pages/AnalyzePage')) },
          { path: '/analyze/jobs/:jobId', handle: { title: 'Nuevo análisis' }, lazy: page(() => import('@/features/analysis/pages/AnalyzePage')) },
          { path: '/repos', handle: { title: 'Repositorios' }, lazy: page(() => import('@/features/repos/pages/ReposPage')) },
          { path: '/team', handle: { title: 'Equipo' }, lazy: page(() => import('@/features/team/pages/TeamPage')) },
          { path: '/join/:code', handle: { title: 'Unirse a un equipo' }, lazy: page(() => import('@/features/team/pages/JoinTeamPage')) },
          {
            path: '/repos/:repoId',
            children: [
              { path: 'reports/:reportId', handle: { title: 'Reporte' }, lazy: page(() => import('@/features/report/pages/ReportPage')) },
              { path: 'files', handle: { title: 'Archivos' }, lazy: page(() => import('@/features/repos/pages/RepoFilesPage')) },
              { path: 'editor', handle: { title: 'Editor de código' }, lazy: page(() => import('@/features/editor/pages/EditorPage')) },
              { path: 'assistant', handle: { title: 'Asistente IA' }, lazy: page(() => import('@/features/assistant/pages/AssistantPage')) },
              { path: 'compare', handle: { title: 'Comparativa' }, lazy: page(() => import('@/features/compare/pages/ComparePage')) },
              { path: 'settings', handle: { title: 'Configuración' }, lazy: page(() => import('@/features/settings/pages/SettingsPage')) },
            ],
          },
        ],
      },
    ],
  },
  { path: '*', lazy: page(() => import('@/app/NotFoundPage')) },
])

// Permite navegar desde fuera de componentes (acciones de toasts, stores)
setNavigator((to) => void router.navigate(to))
