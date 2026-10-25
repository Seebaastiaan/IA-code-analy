import { describe, expect, it } from 'vitest'
import { JOB_STEPS, NEXT_STEPS, WHAT_HAPPENS } from '@/features/analysis/constants/jobSteps'

describe('pasos del Sprint 4', () => {
  it('el análisis llega hasta "Creando entorno aislado" (mismo orden que backend/app/analysis/steps.py)', () => {
    expect(JOB_STEPS.map((s) => s.name)).toEqual(['Clonando repositorio', 'Creando entorno aislado'])
    expect(JOB_STEPS[0].command).toContain('{branch}')
  })

  it('lo demás queda anunciado para los siguientes sprints', () => {
    expect(NEXT_STEPS.every((s) => s.sprint > 4)).toBe(true)
    expect(WHAT_HAPPENS.map(([t]) => t)).toEqual(['Clonado', 'Entorno', 'Repositorio'])
  })
})
