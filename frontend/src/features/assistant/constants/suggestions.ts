import type { Report } from '@/features/report/types'

const MAX = 4

/** Para un repo sin reporte (o como relleno) */
export const GENERIC_SUGGESTIONS = [
  '¿Cuáles son los hallazgos más graves?',
  '¿Qué archivos tienen menos cobertura?',
  '¿Qué función conviene refactorizar primero?',
  '¿Cómo subo el score de seguridad?',
]

/**
 * "Prueba preguntar" a partir del último reporte del repo: el hallazgo más grave, otro de seguridad, el
 * archivo con menos cobertura y la función más compleja. "Explícame el hallazgo X en archivo:línea" es el
 * formato que el backend reconoce para meter el código de ese hallazgo en el contexto.
 */
export function buildSuggestions(report: Report | null | undefined): string[] {
  const out: string[] = []
  if (report) {
    // findings ya viene ordenado por severidad
    const open = report.findings.filter((f) => f.status === 'open')
    const worst = open[0]
    if (worst) out.push(`Explícame el hallazgo ${worst.rule} en ${worst.file}:${worst.line}`)
    const sec = open.find((f) => f.cat === 'seg' && f !== worst)
    if (sec) out.push(`¿Cómo corrijo ${sec.rule} en ${sec.file}?`)
    const lowCov = [...report.coverage].sort((a, b) => a.percent - b.percent)[0]
    if (lowCov && lowCov.percent < 100) out.push(`¿Qué pruebas le faltan a ${lowCov.file}?`)
    const complex = [...report.complexity].sort((a, b) => b.cc - a.cc)[0]
    if (complex) out.push(`¿Cómo simplifico ${complex.fn}()?`)
  }
  for (const g of GENERIC_SUGGESTIONS) if (out.length < MAX && !out.includes(g)) out.push(g)
  return out.slice(0, MAX)
}
