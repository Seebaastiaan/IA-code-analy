import { paths } from '@/shared/constants/paths'
import type { IconName } from '@/shared/ui/Icon'

export interface NavItem {
  id: string
  label: string
  icon: IconName
  /** Recibe el repo activo; devuelve null si el enlace necesita repo y no hay ninguno */
  to: (repoId: string | null) => string
  /** Activo también en otras URLs (p. ej. /analyze/jobs/:id cuenta como "Nuevo análisis") */
  match?: (pathname: string) => boolean
}

export interface NavGroup {
  group: string
  items: NavItem[]
}

// Sin repo seleccionado, los enlaces del repo activo llevan a la lista de repositorios
const scoped = (fn: (repoId: string) => string) => (repoId: string | null) => (repoId ? fn(repoId) : paths.repos())

/**
 * Sprint 6: tablero con el score, análisis completo (10 pasos), repositorios y configuración. Reporte,
 * editor, asistente IA y comparativa se agregan en los siguientes sprints.
 */
export const NAV: NavGroup[] = [
  {
    group: 'Principal',
    items: [
      { id: 'dashboard', label: 'Tablero', icon: 'home', to: paths.dashboard },
      { id: 'analyze', label: 'Nuevo análisis', icon: 'plus', to: () => paths.analyze(), match: (p) => p.startsWith('/analyze/') },
      { id: 'repos', label: 'Repositorios', icon: 'folder', to: paths.repos },
      { id: 'files', label: 'Archivos', icon: 'file', to: scoped((id) => paths.files(id)) },
    ],
  },
  {
    group: 'Sistema',
    items: [
      { id: 'settings', label: 'Configuración', icon: 'sliders', to: scoped(paths.settings) },
      { id: 'team', label: 'Equipo', icon: 'users', to: paths.team },
    ],
  },
]
