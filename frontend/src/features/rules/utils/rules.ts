import type { CHIP_TONES } from '@/shared/ui/styles'
import type { BusinessRuleResult, RuleLevel, RuleStatus, TestOutcome } from '../types'

type Tone = keyof typeof CHIP_TONES

export const STATUS: Record<RuleStatus, { label: string; tone: Tone; order: number }> = {
  no_cumple: { label: 'No cumple', tone: 'danger', order: 0 },
  sin_verificar: { label: 'Sin verificar', tone: 'neutral', order: 1 },
  cumple: { label: 'Cumple', tone: 'success', order: 2 },
}

export const LEVEL: Record<RuleLevel, string> = {
  pruebas: 'Pruebas',
  patron: 'Patrón',
  pruebas_y_patron: 'Pruebas y patrón',
  ninguno: 'Sin verificación',
}

export const OUTCOME: Record<TestOutcome, { label: string; tone: Tone }> = {
  passed: { label: 'Pasa', tone: 'success' },
  failed: { label: 'Falla', tone: 'danger' },
  error: { label: 'Error', tone: 'danger' },
  skipped: { label: 'Omitida', tone: 'neutral' },
  not_run: { label: 'No corrió', tone: 'neutral' },
  sin_ejecutar: { label: 'Sin ejecutar', tone: 'neutral' },
}

export type StatusFilter = RuleStatus | 'todas'

/** Reglas con ese estado; las que no cumplen primero y, dentro de cada estado, en el orden del archivo. */
export function filterRules(rules: BusinessRuleResult[], status: StatusFilter): BusinessRuleResult[] {
  return rules
    .map((r, i) => ({ r, i }))
    .filter(({ r }) => status === 'todas' || r.status === status)
    .sort((a, b) => STATUS[a.r.status].order - STATUS[b.r.status].order || a.i - b.i)
    .map(({ r }) => r)
}

/** "test_rn002_…": nombre alternativo al marcador para una regla. */
export const testName = (ruleId: string) => `test_${ruleId.replace('-', '').toLowerCase()}_…`

/** Archivo de pytest y nombre de la función de un nodeid (tests/test_x.py::TestA::test_b → test_b). */
export const testFunction = (nodeid: string) => nodeid.split('::').slice(1).join('::') || nodeid

/** Descarga un texto como archivo (el reglas_negocio.toml para subirlo al repositorio). */
export function saveText(name: string, text: string, type = 'application/toml') {
  const url = URL.createObjectURL(new Blob([text], { type: `${type};charset=utf-8` }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}
