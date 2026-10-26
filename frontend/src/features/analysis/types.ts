export type JobStatus = 'running' | 'error' | 'done' | 'cancelled'

export interface JobError {
  title: string
  detail: string
  hint?: string
}

export interface Job {
  id: string
  url: string
  /** "equipo/api-pagos" */
  name: string
  branch: string
  /** Índice del paso actual (0-based) */
  step: number
  total: number
  status: JobStatus
  logs: string[]
  error?: JobError
  repo_id?: string
  /** Disponible al terminar */
  report_id?: string
}

/** Mensajes del servidor por WS /ws/jobs/{id} (docs/FRONTEND_SPEC.md §6.3) */
export type JobMessage =
  | { type: 'snapshot'; job: Job }
  | { type: 'step'; index: number; total: number; name: string; command: string }
  | { type: 'log'; line: string }
  | { type: 'step_done'; index: number }
  | ({ type: 'error'; step: number } & JobError)
  | { type: 'done'; repo_id: string; report_id: string; num: number; score: number }

export type AnalyzerId = 'bandit' | 'pip-audit' | 'pytest' | 'coverage' | 'ruff' | 'radon'

export interface AnalyzeRequest {
  url: string
  branch: string
  analyzers: AnalyzerId[]
  sandbox: boolean
}

export interface AnalyzeResponse {
  job_id: string
}
