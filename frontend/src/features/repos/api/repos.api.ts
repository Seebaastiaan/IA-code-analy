import { queryOptions, useQuery } from '@tanstack/react-query'
import { EP } from '@/shared/api/endpoints'
import { http } from '@/shared/api/http'
import type { FileResponse, ReanalyzeResponse, Repo, TreeEntry } from '../types'

export const reposApi = {
  list: () => http.get<Repo[]>(EP.repos.list),
  reanalyze: (repoId: string) => http.post<ReanalyzeResponse>(EP.repos.analyze(repoId)),
  tree: (repoId: string) => http.get<TreeEntry[]>(EP.repos.tree(repoId)),
}

// Mientras haya análisis en curso, la lista se refresca para mostrar el avance
export const useRepos = () =>
  useQuery({
    queryKey: ['repos'],
    queryFn: reposApi.list,
    refetchInterval: (q) => (q.state.data?.some((r) => r.status === 'analizando') ? 3000 : false),
  })

export const useRepoTree = (repoId: string) => useQuery({ queryKey: ['tree', repoId], queryFn: () => reposApi.tree(repoId) })

export const fileQuery = (repoId: string, path: string) =>
  queryOptions({
    queryKey: ['file', repoId, path],
    queryFn: () => http.get<FileResponse>(EP.file, { repo: repoId, path }),
    staleTime: Infinity,
  })

/** Archivo del último clon, en solo lectura. */
export const useFile = (repoId: string, path: string | null) => useQuery({ ...fileQuery(repoId, path ?? ''), enabled: Boolean(path) })

/** Un repo de la lista (comparte caché con la pantalla de repositorios). */
export function useRepo(repoId: string | null | undefined) {
  const query = useRepos()
  return { ...query, data: query.data?.find((r) => r.id === repoId) }
}
