import type { Finding } from '@/features/findings/types'
import type { Scores } from '@/shared/types/common'

export interface AnalysisOption {
  /** id de reporte ("r1-127") o "branch:<nombre>" para el último de una rama */
  id: string
  label: string
}

export interface DiffRequest {
  base: string
  target: string
}

export interface DiffResponse {
  a: Scores
  b: Scores
  new: Finding[]
  resolved: Finding[]
}
