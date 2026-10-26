import type { RepoStatus, Scores, Severity } from '@/shared/types/common'

export interface Repo {
  id: string
  /** "equipo/api-pagos" */
  name: string
  url: string
  branch: string
  commit: string | null
  status: RepoStatus
  last_analyzed_at: string | null
  files: number
  last_report_id: string | null
  last_report_num: number | null
  scores: Scores | null
  /** Mensaje del último error, si status = error */
  error: string | null
  /** Progreso del job en curso, si status = analizando */
  progress: { job_id: string; step: number; total: number; name: string } | null
}

export interface TreeEntry {
  path: string
  /** Carpeta contenedora ('' = raíz) */
  dir: string
  open_findings: number
  worst: Severity | null
}

export interface ReanalyzeResponse {
  job_id: string
}
