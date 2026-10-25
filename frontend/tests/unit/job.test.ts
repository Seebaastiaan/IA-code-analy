import { describe, expect, it } from 'vitest'
import { reduceJob } from '@/features/analysis/store/job.store'
import type { Job } from '@/features/analysis/types'

const base: Job = { id: 'job-1', url: 'https://github.com/e/r', name: 'e/r', branch: 'main', step: 0, total: 2, status: 'running', logs: [] }

describe('reduceJob', () => {
  it('el snapshot reemplaza el estado (reconexión)', () => {
    expect(reduceJob(null, { type: 'snapshot', job: { ...base, step: 4 } })?.step).toBe(4)
  })

  it('ignora mensajes antes del snapshot', () => {
    expect(reduceJob(null, { type: 'log', line: 'x' })).toBeNull()
  })

  it('acumula logs y avanza pasos', () => {
    let j = reduceJob(base, { type: 'log', line: 'hola' })
    j = reduceJob(j, { type: 'step_done', index: 0 })
    expect(j?.logs).toEqual(['hola'])
    expect(j?.step).toBe(1)
  })

  it('marca error con detalle', () => {
    const j = reduceJob(base, { type: 'error', step: 1, title: 't', detail: 'd', hint: 'h' })
    expect(j).toMatchObject({ status: 'error', step: 1, error: { title: 't', detail: 'd', hint: 'h' } })
  })

  it('al terminar guarda el análisis en el repositorio y llega al 100 %', () => {
    const j = reduceJob(base, { type: 'done', repo_id: 'r1', report_id: 'r1-4', num: 4 })
    expect(j).toMatchObject({ status: 'done', step: 2, repo_id: 'r1', report_id: 'r1-4' })
  })
})
