import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { EP } from '@/shared/api/endpoints'
import { http } from '@/shared/api/http'
import type { DashboardResponse } from '../types'

export const useDashboard = (repoId: string | null) =>
  useQuery({
    queryKey: ['dashboard', repoId],
    queryFn: () => http.get<DashboardResponse>(EP.dashboard, { repo: repoId }),
    // Al cambiar de repo se mantiene el tablero anterior hasta que llegue el nuevo
    placeholderData: keepPreviousData,
  })
