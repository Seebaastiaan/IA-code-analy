import { useMutation, useQueryClient } from '@tanstack/react-query'
import { configApi, configQuery } from '@/features/settings'
import { invalidateAnalysis } from '@/shared/api/invalidate'
import { paths } from '@/shared/constants/paths'
import { toast } from '@/shared/hooks/useToast'
import { navigateTo } from '@/shared/utils/navigation'

/** Agrega una regla a las ignoradas del proyecto (.ia_voy.toml). */
export function useIgnoreRule(repoId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (rule: string) => {
      const config = await queryClient.fetchQuery(configQuery(repoId))
      if (config.ignored.includes(rule)) return config
      return configApi.save(repoId, { ...config, ignored: [...config.ignored, rule] })
    },
    onSuccess: (config, rule) => {
      queryClient.setQueryData(configQuery(repoId).queryKey, config)
      void invalidateAnalysis(queryClient)
      toast(
        `Regla ${rule} agregada a la lista de ignoradas`,
        { action: { label: 'Ver ajustes', onClick: () => navigateTo(paths.settings(repoId)) } },
      )
    },
    onError: (e) => toast(e.message, { tone: 'err' }),
  })
}
