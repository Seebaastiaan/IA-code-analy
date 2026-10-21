import { EP } from '@/shared/api/endpoints'
import { http } from '@/shared/api/http'
import type { ShareRequest, ShareResponse } from '../types'

export const shareApi = {
  create: (reportId: string, body: ShareRequest) => http.post<ShareResponse>(EP.report.share(reportId), body),
}
