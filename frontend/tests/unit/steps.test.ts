import { describe, expect, it } from 'vitest'
import { JOB_STEPS, NEXT_STEPS, WHAT_HAPPENS } from '@/features/analysis/constants/jobSteps'

describe('pasos del Sprint 5', () => {
  it('el análisis llega hasta pip-audit (mismo orden que backend/app/analysis/steps.py)', () => {
    expect(JOB_STEPS.map((s) => s.name)).toEqual(['Clonando repositorio', 'Creando entorno aislado', 'Instalando dependencias', 'Bandit', 'pip-audit'])
    expect(JOB_STEPS[0].command).toContain('{branch}')
  })

  it('lo demás queda anunciado para los siguientes sprints', () => {
    expect(NEXT_STEPS.every((s) => s.sprint > 5)).toBe(true)
    expect(NEXT_STEPS.map((s) => s.name)).toContain('Calculando score')
    expect(WHAT_HAPPENS.map(([t]) => t)).toEqual(['Clonado', 'Entorno', 'Dependencias', 'Seguridad', 'Repositorio'])
  })
})
