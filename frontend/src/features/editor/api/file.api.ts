import { queryOptions, useQuery } from '@tanstack/react-query'
import type { FixRequest, FixResponse } from '@/features/findings/types'
import { EP } from '@/shared/api/endpoints'
import { http } from '@/shared/api/http'
import type { FileResponse, SaveFileRequest, SaveFileResponse } from '../types'

export const fileQuery = (repoId: string, path: string) =>
  queryOptions({
    queryKey: ['file', repoId, path],
    queryFn: () => http.get<FileResponse>(EP.file, { repo: repoId, path }),
    staleTime: Infinity,
  })

export const useFile = (repoId: string, path: string | null) => useQuery({ ...fileQuery(repoId, path ?? ''), enabled: Boolean(path) })

export const fileApi = {
  save: (body: SaveFileRequest) => http.put<SaveFileResponse>(EP.file, body),
  fix: (body: FixRequest) => http.post<FixResponse>(EP.fix, body),
}
