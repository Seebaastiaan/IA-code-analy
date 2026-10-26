import { describe, expect, it } from 'vitest'
import { JOB_STEPS, NEXT_STEPS, WHAT_HAPPENS } from '@/features/analysis/constants/jobSteps'

describe('pasos del Sprint 6', () => {
  it('el análisis llega hasta el score (mismo orden que backend/app/analysis/fake.py)', () => {
    expect(JOB_STEPS).toHaveLength(10)
    expect(JOB_STEPS.slice(5).map((s) => s.name)).toEqual(['pytest', 'coverage', 'Ruff', 'Radon', 'Calculando score'])
    expect(JOB_STEPS[0].command).toContain('{branch}')
  })

  it('lo demás queda anunciado para los siguientes sprints', () => {
    expect(NEXT_STEPS).toEqual([{ name: 'Indexando para el asistente', sprint: 7 }])
    expect(WHAT_HAPPENS.map(([t]) => t)).toEqual(['Clonado', 'Entorno', 'Análisis', 'Score', 'Tablero'])
  })
})
