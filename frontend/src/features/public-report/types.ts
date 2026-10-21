import type { Finding } from '@/features/findings/types'
import type { Scores } from '@/shared/types/common'

export interface PublicReport {
  repo_name: string
  branch: string
  commit: string
  created_at: string
  scores: Scores
  /** Solo severidad alta y media */
  findings: Finding[]
  shared_by: string
  expires_at: string | null
  include_code: boolean
}

export interface UnlockResponse {
  token: string
}
