import type { RepoStatus } from '@/shared/types/common'

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
  /** Análisis guardados del repo */
  reports: number
  /** Mensaje del último error, si status = error */
  error: string | null
  /** Progreso del job en curso, si status = analizando */
  progress: { job_id: string; step: number; total: number; name: string } | null
}

/** Un análisis guardado en el repositorio (Sprint 4: hasta el entorno aislado, sin hallazgos ni score). */
export interface SavedReport {
  id: string
  num: number
  branch: string
  commit: string
  created_at: string
  duration_s: number
  languages: { name: string; files: number }[]
}

export interface TreeEntry {
  path: string
  /** Carpeta contenedora ('' = raíz) */
  dir: string
}

export interface FileResponse {
  path: string
  language: string
  content: string
}

export interface ReanalyzeResponse {
  job_id: string
}
