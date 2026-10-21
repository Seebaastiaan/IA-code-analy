import { useQuery } from '@tanstack/react-query'
import { EP } from '@/shared/api/endpoints'
import { http } from '@/shared/api/http'
import type { AnalysisOption, DiffResponse } from '../types'

export const useAnalyses = (repoId: string) =>
  useQuery({ queryKey: ['analyses', repoId], queryFn: () => http.get<AnalysisOption[]>(EP.repos.analyses(repoId)) })

export const useDiff = (base: string | null, target: string | null) =>
  useQuery({
    queryKey: ['diff', base, target],
    queryFn: () => http.post<DiffResponse>(EP.diff, { base, target }),
    enabled: Boolean(base && target),
  })
