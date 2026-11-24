import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useJobStore } from '@/features/analysis/store/job.store'
import { TEAM_KEY } from '@/features/team/api/team.api'
import { invalidateAnalysis } from '@/shared/api/invalidate'
import { toast } from '@/shared/hooks/useToast'
import { reposApi } from '../api/repos.api'
import { useSelectedRepo } from '../store/selectedRepo.store'
import type { Repo } from '../types'

export function useRemoveRepo() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (repo: Repo) => reposApi.remove(repo.id),
    onSuccess: async (_, repo) => {
      const selection = useSelectedRepo.getState()
      if (selection.repoId === repo.id) selection.select(null)
      useJobStore.getState().forgetRepo(repo.id)

      await queryClient.cancelQueries({ queryKey: ['repos'] })
      queryClient.setQueryData<Repo[]>(['repos'], (repos) => repos?.filter((entry) => entry.id !== repo.id))
      queryClient.removeQueries({ queryKey: ['dashboard'] })
      for (const key of ['report', 'tree', 'file', 'config', 'analyses', 'index']) {
        queryClient.removeQueries({ queryKey: [key, repo.id] })
      }
      toast(`Se quitó ${repo.name} del analizador`)
      await Promise.all([invalidateAnalysis(queryClient), queryClient.invalidateQueries({ queryKey: TEAM_KEY })])
    },
    onError: (error) => toast(error.message, { tone: 'err' }),
  })
}
