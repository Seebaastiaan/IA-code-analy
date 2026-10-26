import type { QueryClient } from '@tanstack/react-query'

/**
 * Consultas que dependen del resultado de un análisis. Tras guardar un archivo, aplicar un fix,
 * cambiar la configuración o terminar un job, todas quedan obsoletas.
 */
const ANALYSIS_ROOTS = ['dashboard', 'repos', 'report', 'tree', 'analyses', 'diff', 'index'] as const

export function invalidateAnalysis(queryClient: QueryClient) {
  return Promise.all(ANALYSIS_ROOTS.map((key) => queryClient.invalidateQueries({ queryKey: [key] })))
}
