import { Outlet } from 'react-router'

/** Pantallas sin sidebar ni header de la app: login y vista pública. */
export function SoloLayout() {
  return <Outlet />
}
