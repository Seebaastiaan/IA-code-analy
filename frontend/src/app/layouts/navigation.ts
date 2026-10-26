import { paths } from '@/shared/constants/paths'
import type { IconName } from '@/shared/ui/Icon'

export interface NavItem {
  id: string
  label: string
  icon: IconName
  /** Recibe el repo activo; devuelve null si el enlace necesita repo y no hay ninguno */
  to: (repoId: string | null) => string
  /** Activo también en otras URLs (p. ej. el enlace va a /reports/latest pero se ve /reports/r1-128) */
  match?: (pathname: string) => boolean
}

export interface NavGroup {
  group: string
  items: NavItem[]
}

// Sin repo seleccionado, los enlaces de análisis llevan a la lista de repositorios
const scoped = (fn: (repoId: string) => string) => (repoId: string | null) => (repoId ? fn(repoId) : paths.repos())

export const NAV: NavGroup[] = [
  {
    group: 'Principal',
    items: [
      { id: 'dashboard', label: 'Tablero', icon: 'home', to: paths.dashboard },
      { id: 'analyze', label: 'Nuevo análisis', icon: 'plus', to: () => paths.analyze() },
      { id: 'repos', label: 'Repositorios', icon: 'folder', to: paths.repos },
    ],
  },
  {
    group: 'Análisis',
    items: [
      { id: 'report', label: 'Reporte', icon: 'doc', to: scoped((id) => paths.report(id)), match: (p) => /^\/repos\/[^/]+\/reports\//.test(p) },
      { id: 'editor', label: 'Editor', icon: 'code', to: scoped((id) => paths.editor(id)) },
      { id: 'assistant', label: 'Asistente IA', icon: 'chat', to: scoped(paths.assistant) },
      { id: 'compare', label: 'Comparativa', icon: 'compare', to: scoped(paths.compare) },
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
