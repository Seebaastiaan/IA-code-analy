import { useMutation, useQueryClient } from '@tanstack/react-query'
import { invalidateAnalysis } from '@/shared/api/invalidate'
import { paths } from '@/shared/constants/paths'
import { toast } from '@/shared/hooks/useToast'
import { f1 } from '@/shared/utils/score'
import { navigateTo } from '@/shared/utils/navigation'
import { fileApi, fileQuery } from '../api/file.api'
import { fileKey, useEditorStore } from '../store/editor.store'

/** Guarda el borrador; el backend re-analiza el archivo y devuelve el efecto en el score. */
export function useSaveFile(repoId: string, path: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (content: string) => fileApi.save({ repo_id: repoId, path, content }),
    onSuccess: (res, content) => {
      const key = fileKey(repoId, path)
      queryClient.setQueryData(fileQuery(repoId, path).queryKey, (old) => (old ? { ...old, content } : old))
      useEditorStore.getState().discard(key)
      void invalidateAnalysis(queryClient)
      const delta = res.score_after !== res.score_before
      toast(
        <>
          Guardado y re-analizado.{' '}
          {delta ? (
            <>
              Score: <b>{f1(res.score_before)}</b> → <b className="text-emerald-600 dark:text-emerald-400">{f1(res.score_after)}</b>
            </>
          ) : (
            'Sin cambios en el score.'
          )}
        </>,
        { ms: 6000, action: { label: 'Ver tablero', onClick: () => navigateTo(paths.dashboard()) } },
      )
    },
    onError: (e) => toast(`No se pudo guardar: ${e.message}`, { tone: 'err' }),
  })
}
