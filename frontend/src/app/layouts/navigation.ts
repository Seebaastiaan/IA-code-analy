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

// Sin repo seleccionado, el enlace del reporte lleva a analizar uno
const scoped = (fn: (repoId: string) => string) => (repoId: string | null) => (repoId ? fn(repoId) : paths.analyze())

export const NAV: NavGroup[] = [
  {
    group: 'Principal',
    items: [{ id: 'analyze', label: 'Nuevo análisis', icon: 'plus', to: () => paths.analyze() }],
  },
  {
    group: 'Análisis',
    items: [{ id: 'report', label: 'Reporte', icon: 'doc', to: scoped((id) => paths.report(id)), match: (p) => /^\/repos\/[^/]+\/reports\//.test(p) }],
  },
]
