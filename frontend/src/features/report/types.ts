import type { AnalyzerId } from '@/features/analysis/types'
import type { Finding } from '@/features/findings/types'
import type { Grade } from '@/shared/constants/grades'
import type { Scores, Thresholds, Weights } from '@/shared/types/common'

export interface Report {
  /** "r1-128" */
  id: string
  num: number
  repo_id: string
  repo_name: string
  branch: string
  commit: string
  created_at: string
  duration_s: number
  scores: Scores
  prev: { num: number; scores: Scores } | null
  weights: Weights
  thresholds: Thresholds
  findings: Finding[]
  coverage: { file: string; percent: number }[]
  complexity: { fn: string; file: string; cc: number; grade: Grade }[]
  /** coverage_total null: no se eligió coverage en este análisis */
  summary: { coverage_total: number | null; tests_failed: number; avg_complexity: number }
  /** Analizadores que corrieron; los que faltan no aportan hallazgos ni métricas */
  analyzers: AnalyzerId[]
  /** Lenguajes del repo por número de archivos (solo se analiza Python); vacío en reportes anteriores */
  languages: { name: string; files: number }[]
}

export type ExportFormat = 'json' | 'html' | 'md' | 'sarif'
