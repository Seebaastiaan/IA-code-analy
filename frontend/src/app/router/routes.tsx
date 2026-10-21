import { createBrowserRouter, Navigate } from 'react-router'
import { SoloLayout } from '@/app/layouts/SoloLayout'
import { setNavigator } from '@/shared/utils/navigation'

/** Cada página se carga bajo demanda. */
const page = (load: () => Promise<{ default: React.ComponentType }>) => async () => ({ Component: (await load()).default })

export const router = createBrowserRouter([
  {
    Component: SoloLayout,
    children: [
      // Prototipo del Sprint 3: una sola pantalla (URL del repo → diagnóstico de la IA)
      { index: true, lazy: page(() => import('@/features/diagnostico/pages/DiagnosticoPage')) },
      { path: '/dashboard', element: <Navigate to="/" replace /> },
    ],
  },
  { path: '*', lazy: page(() => import('@/app/NotFoundPage')) },
])

// Permite navegar desde fuera de componentes (acciones de toasts, stores)
setNavigator((to) => void router.navigate(to))
