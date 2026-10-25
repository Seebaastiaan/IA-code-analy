import type { QueryClient } from '@tanstack/react-query'

/**
 * Consultas que dependen del resultado de un análisis. Tras cambiar la configuración o terminar un job,
 * todas quedan obsoletas.
 */
const ANALYSIS_ROOTS = ['repos', 'history', 'tree', 'file'] as const

export function invalidateAnalysis(queryClient: QueryClient) {
  return Promise.all(ANALYSIS_ROOTS.map((key) => queryClient.invalidateQueries({ queryKey: [key] })))
}
