import { describe, expect, it } from 'vitest'
import type { RulePreview } from '@/features/rules/types'
import { currentStep, nextAction } from '@/features/rules/utils/steps'

const rule = (over: Partial<RulePreview> = {}): RulePreview => ({ id: 'RN-001', title: 'Regla', severity: 'alta', status: 'borrador', doubts: [], ...over }) as RulePreview

describe('nextAction', () => {
  it('con contradicciones pendientes, lo siguiente es decidir cuál regla vale', () => {
    expect(nextAction([], 2)).toMatchObject({ step: 0, label: 'Decidir' })
    expect(nextAction([], 1).text).toContain('un punto')
  })

  it('sin contradicciones sigue el orden de siempre', () => {
    expect(nextAction([]).label).toBe('Importar')
    expect(nextAction([rule({ doubts: ['¿incluye el valor exacto?'] })]).label).toBe('Contestar')
    expect(currentStep([rule()])).toBe(2)
  })
})
