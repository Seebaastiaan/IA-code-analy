import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useJobStore } from '@/features/analysis'
import { paths } from '@/shared/constants/paths'
import { toast } from '@/shared/hooks/useToast'
import { navigateTo } from '@/shared/utils/navigation'
import { reposApi } from '../api/repos.api'
import type { Repo } from '../types'

/** Encola un re-análisis y sigue su progreso en el JobPill. */
export function useReanalyze() {
  const queryClient = useQueryClient()
  const connect = useJobStore((s) => s.connect)
  return useMutation({
    mutationFn: (repo: Repo) => reposApi.reanalyze(repo.id),
    onSuccess: ({ job_id }, repo) => {
      connect(job_id)
      void queryClient.invalidateQueries({ queryKey: ['repos'] })
      toast(`Re-análisis de ${repo.name} en cola`, { tone: 'info', action: { label: 'Ver progreso', onClick: () => navigateTo(paths.job(job_id)) } })
    },
    onError: (e) => toast(e.message, { tone: 'err' }),
  })
}
