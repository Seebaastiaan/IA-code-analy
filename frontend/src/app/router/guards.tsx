import { Navigate, Outlet, useLocation } from 'react-router'
import { useSession } from '@/features/auth'
import { paths } from '@/shared/constants/paths'

/** Rutas privadas: sin token, manda a login recordando a dónde quería ir. */
export function RequireAuth() {
  const token = useSession((s) => s.token)
  const location = useLocation()
  if (!token) return <Navigate to={paths.login()} replace state={{ from: location.pathname + location.search }} />
  return <Outlet />
}

/** Login: si ya hay sesión, va directo al tablero. */
export function RedirectIfAuth() {
  const token = useSession((s) => s.token)
  if (token) return <Navigate to={paths.dashboard()} replace />
  return <Outlet />
}
