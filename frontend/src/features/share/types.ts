export type ExpiryDays = 0 | 1 | 7 | 30

export interface ShareRequest {
  password: string | null
  /** 0 = nunca expira */
  expires_days: ExpiryDays
  include_code: boolean
}

export interface ShareResponse {
  share_id: string
  url: string
  expires_at: string | null
}
