import { EP } from '@/shared/api/endpoints'
import { http } from '@/shared/api/http'
import type { AnalyzeRequest, AnalyzeResponse, Job } from '../types'

export const analysisApi = {
  start: (body: AnalyzeRequest) => http.post<AnalyzeResponse>(EP.analyze, body),
  get: (jobId: string) => http.get<Job>(EP.jobs.get(jobId)),
  cancel: (jobId: string) => http.delete<void>(EP.jobs.get(jobId)),
  retry: (jobId: string) => http.post<AnalyzeResponse>(EP.jobs.retry(jobId)),
}
