import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { Finding } from '@/features/findings/types'
import { paths } from '@/shared/constants/paths'
import { toast } from '@/shared/hooks/useToast'
import { navigateTo } from '@/shared/utils/navigation'
import { fileApi, fileQuery } from '../api/file.api'
import { fileKey, useEditorStore } from '../store/editor.store'
import { applyPatches } from '../utils/patches'

/**
 * Pide al backend los parches de uno o varios hallazgos, los aplica sobre el borrador del archivo
 * y abre el editor en modo diff para revisarlos antes de guardar.
 */
export function useApplyFix(repoId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (findings: Finding[]) => {
      const { patches } = await fileApi.fix({ repo_id: repoId, finding_ids: findings.map((f) => f.id) })
      const files = [...new Set(patches.map((p) => p.file))]
      let missed = 0
      for (const path of files) {
        const file = await queryClient.fetchQuery(fileQuery(repoId, path))
        const key = fileKey(repoId, path)
        const store = useEditorStore.getState()
        const result = applyPatches(store.drafts[key] ?? file.content, patches.filter((p) => p.file === path))
        missed += result.missed
        store.applyFix(key, result.content, findings.filter((f) => f.file === path).map((f) => f.id))
      }
      return { file: files[0] ?? findings[0]?.file, missed }
    },
    onSuccess: ({ file, missed }) => {
      if (file) navigateTo(paths.editor(repoId, { file, diff: true }))
      if (missed) toast('Parte de la corrección no se pudo aplicar: el código cambió. Revisa el diff.', { tone: 'err' })
      else toast('Corrección aplicada. Revisa el diff y guarda.', { tone: 'info' })
    },
    onError: (e) => toast(e.message, { tone: 'err' }),
  })
}
