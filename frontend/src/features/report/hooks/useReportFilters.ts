import { useSearchParams } from 'react-router'
import type { Category, Severity } from '@/shared/types/common'

export type ReportTab = 'hallazgos' | 'cobertura' | 'complejidad'
export type SevFilter = Severity | 'todas'
export type CatFilter = Category | 'todas'

/** Filtros y pestaña del reporte en la URL (?tab=&q=&sev=&cat=): se pueden compartir y sobreviven a recargar. */
export function useReportFilters() {
  const [params, setParams] = useSearchParams()
  const filters = {
    tab: (params.get('tab') ?? 'hallazgos') as ReportTab,
    q: params.get('q') ?? '',
    sev: (params.get('sev') ?? 'todas') as SevFilter,
    cat: (params.get('cat') ?? 'todas') as CatFilter,
  }

  const set = (patch: Partial<typeof filters>) =>
    setParams(
      (p) => {
        for (const [k, v] of Object.entries(patch)) {
          const isDefault = v === '' || v === 'todas' || (k === 'tab' && v === 'hallazgos')
          if (isDefault) p.delete(k)
          else p.set(k, v)
        }
        return p
      },
      { replace: true },
    )

  const clear = () => set({ q: '', sev: 'todas', cat: 'todas' })

  return { ...filters, set, clear }
}
