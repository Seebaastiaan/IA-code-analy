import { queryOptions, useQuery } from '@tanstack/react-query'
import { EP } from '@/shared/api/endpoints'
import { http } from '@/shared/api/http'
import type { HealthResponse, ProjectConfig } from '../types'

export const configApi = {
  get: (projectId: string) => http.get<ProjectConfig>(EP.config(projectId)),
  save: (projectId: string, config: ProjectConfig) => http.put<ProjectConfig>(EP.config(projectId), config),
  health: () => http.get<HealthResponse>(EP.health),
}

export const configQuery = (projectId: string) => queryOptions({ queryKey: ['config', projectId], queryFn: () => configApi.get(projectId) })

export const useConfig = (projectId: string) => useQuery({ ...configQuery(projectId), enabled: Boolean(projectId) })

/** Estado de servicios; se refresca cada minuto (sidebar y configuración). */
export const useHealth = () => useQuery({ queryKey: ['health'], queryFn: configApi.health, refetchInterval: 60_000 })
