import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from '@/shared/hooks/useToast'
import { reposApi } from '../api/repos.api'
import { useSelectedRepo } from '../store/selectedRepo.store'
import type { Repo } from '../types'

/** Elimina un repositorio del equipo con todos sus análisis (no toca el de GitHub). */
export function useDeleteRepo(onDone?: () => void) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (repo: Repo) => reposApi.remove(repo.id),
    onSuccess: (_, repo) => {
      if (useSelectedRepo.getState().repoId === repo.id) useSelectedRepo.getState().clear()
      void queryClient.invalidateQueries({ queryKey: ['repos'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.removeQueries({ queryKey: ['tree', repo.id] })
      toast(`Se eliminó ${repo.name}`, { tone: 'ok' })
      onDone?.()
    },
    onError: (e) => toast(e.message, { tone: 'err' }),
  })
}
