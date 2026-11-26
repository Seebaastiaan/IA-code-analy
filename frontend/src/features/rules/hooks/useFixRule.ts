import { toastError } from '../utils/errors'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { fileQuery } from '@/features/editor/api/file.api'
import { fileKey, useEditorStore } from '@/features/editor/store/editor.store'
import { applyPatches } from '@/features/editor/utils/patches'
import { paths } from '@/shared/constants/paths'
import { toast } from '@/shared/hooks/useToast'
import { navigateTo } from '@/shared/utils/navigation'
import { rulesApi } from '../api/rules.api'

/**
 * «El documento manda» (docs/PLAN_REGLAS_AUTOMATICO.md, caso 2): la IA propone el cambio en el código para que cumpla
 * la regla. Los parches se aplican al borrador del editor y se abre el diff: nada se guarda hasta que la persona lo revisa.
 */
export function useFixRule(repoId: string) {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: async (ruleId: string) => {
      const { patches, notes = [] } = await rulesApi.fixCode(repoId, ruleId)
      let missed = 0
      const files = [...new Set(patches.map((p) => p.file))]
      for (const path of files) {
        const current = await queryClient.fetchQuery(fileQuery(repoId, path))
        const key = fileKey(repoId, path)
        const store = useEditorStore.getState()
        const result = applyPatches(store.drafts[key] ?? current.content, patches.filter((p) => p.file === path))
        missed += result.missed
        store.applyFix(key, result.content, [])
      }
      return { files, missed, notes }
    },
    onSuccess: ({ files, missed, notes }) => {
      navigateTo(paths.editor(repoId, { file: files[0], diff: true }))
      if (missed) toast('Parte de la corrección no se pudo aplicar porque el código cambió. Revisa el diff.', { tone: 'err' })
      else toast(notes.length ? `Propuesta de la IA: ${notes.join(' ')} Revisa el diff y guarda.` : 'Corrección lista. Revisa el diff y guarda.', { tone: 'info' })
    },
    onError: (e, ruleId) => toastError(e, () => mutation.mutate(ruleId)),
  })
  return mutation
}
