import { describe, expect, it } from 'vitest'
import { buildSuggestions, GENERIC_SUGGESTIONS } from '@/features/assistant/constants/suggestions'
import type { Report } from '@/features/report/types'

const finding = (id: number, rule: string, file: string, line: number, cat: 'seg' | 'test' | 'prac', status: 'open' | 'resolved' = 'open') =>
  ({ id, sev: 'alta', cat, tool: 'Bandit', rule, file, line, msg: '', why: '', rec: '', fix: false, status }) as Report['findings'][number]

const report = (over: Partial<Report> = {}) =>
  ({
    findings: [finding(1, 'B105', 'auth.py', 15, 'seg'), finding(2, 'B608', 'api.py', 17, 'seg')],
    coverage: [{ file: 'api.py', percent: 45 }, { file: 'utils.py', percent: 90 }],
    complexity: [{ fn: 'cobrar', file: 'pagos.py', cc: 12, grade: 'C' }, { fn: 'suma', file: 'utils.py', cc: 1, grade: 'A' }],
    ...over,
  }) as Report

describe('buildSuggestions', () => {
  it('usa los datos del reporte', () => {
    expect(buildSuggestions(report())).toEqual([
      'Explícame el hallazgo B105 en auth.py:15',
      '¿Cómo corrijo B608 en api.py?',
      '¿Qué pruebas le faltan a api.py?',
      '¿Cómo simplifico cobrar()?',
    ])
  })

  it('ignora hallazgos resueltos y rellena con genéricas', () => {
    const s = buildSuggestions(report({ findings: [finding(1, 'B105', 'auth.py', 15, 'seg', 'resolved')], coverage: [], complexity: [] }))
    expect(s).toEqual(GENERIC_SUGGESTIONS)
  })

  it('sin reporte devuelve las genéricas', () => {
    expect(buildSuggestions(undefined)).toEqual(GENERIC_SUGGESTIONS)
  })
})
