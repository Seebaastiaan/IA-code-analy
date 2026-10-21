import { create } from 'zustand'
import { EP } from '@/shared/api/endpoints'
import { invalidateAnalysis } from '@/shared/api/invalidate'
import { queryClient } from '@/shared/api/queryClient'
import { openSocket } from '@/shared/api/ws'
import { toast } from '@/shared/hooks/useToast'
import { paths } from '@/shared/constants/paths'
import { navigateTo } from '@/shared/utils/navigation'
import { JOB_STEPS } from '../constants/jobSteps'
import type { Job, JobMessage } from '../types'

/** Aplica un mensaje del WebSocket al estado del job. */
export function reduceJob(job: Job | null, m: JobMessage): Job | null {
  if (m.type === 'snapshot') return m.job
  if (!job) return job
  switch (m.type) {
    case 'step':
      return { ...job, step: m.index, total: m.total, status: 'running', error: undefined }
    case 'log':
      return { ...job, logs: [...job.logs, m.line] }
    case 'step_done':
      return { ...job, step: m.index + 1 }
    case 'error':
      return { ...job, status: 'error', step: m.step, error: { title: m.title, detail: m.detail, hint: m.hint } }
    case 'done':
      return { ...job, status: 'done', step: job.total, repo_id: m.repo_id, report_id: m.report_id }
  }
}

/** Efectos visibles de los eventos finales (solo cuando ocurren en vivo, no al reconectar). */
function notify(job: Job, m: JobMessage) {
  if (m.type === 'done') {
    void invalidateAnalysis(queryClient)
    toast('Análisis completado', { action: { label: 'Ver reporte', onClick: () => navigateTo(paths.report(m.repo_id, m.report_id)) } })
  } else if (m.type === 'error') {
    void invalidateAnalysis(queryClient)
    toast(`El análisis falló en ${JOB_STEPS[m.step]?.name ?? 'un paso'}`, { tone: 'err', action: { label: 'Ver detalle', onClick: () => navigateTo(paths.job(job.id)) } })
  }
}

let socket: ReturnType<typeof openSocket> | null = null
let socketJobId: string | null = null

interface JobState {
  /** Análisis seguido por esta pestaña; alimenta el JobPill del header */
  job: Job | null
  /** Se suscribe al WebSocket del job (no reabre si ya está conectado, salvo `force`) */
  connect: (jobId: string, force?: boolean) => void
}

export const useJobStore = create<JobState>((set, get) => ({
  job: null,
  connect: (jobId, force = false) => {
    if (socket && socketJobId === jobId && !force) return
    socket?.close()
    socketJobId = jobId
    if (get().job?.id !== jobId) set({ job: null })
    socket = openSocket<JobMessage>(EP.jobs.socket(jobId), {
      onMessage: (m) => {
        const next = reduceJob(get().job, m)
        set({ job: next })
        if (next) notify(next, m)
      },
    })
  },
}))
