import type { Finding } from '@/features/findings/types'
import type { Repo } from '@/features/repos/types'
import type { Scores, Thresholds } from '@/shared/types/common'

export interface HistoryPoint extends Scores {
  date: string
}

export interface DashboardResponse {
  active_repos: number
  repos: Repo[]
  thresholds: Thresholds
  /** Repo pedido (?repo=) o el primero con reporte; null si aún no hay análisis */
  selected: {
    repo: Repo
    report_id: string
    num: number
    scores: Scores
    prev_scores: Scores | null
    /** Últimos análisis, del más antiguo al actual */
    history: HistoryPoint[]
    top_findings: Finding[]
    open_findings: number
  } | null
}
