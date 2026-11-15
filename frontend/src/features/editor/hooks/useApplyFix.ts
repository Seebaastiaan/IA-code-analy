import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { Finding } from '@/features/findings/types'
import { invalidateAnalysis } from '@/shared/api/invalidate'
import { paths } from '@/shared/constants/paths'
import { toast } from '@/shared/hooks/useToast'
import { navigateTo } from '@/shared/utils/navigation'
import { fileApi, fileQuery } from '../api/file.api'
import { fileKey, useEditorStore } from '../store/editor.store'
import { applyPatches } from '../utils/patches'

/** Archivos que se corrigen a la vez: cada uno puede ser una llamada a la IA */
const CONCURRENCY = 3

type Fixed = { file: string; ok: true; missed: number; notes: string[] }
type Failed = { file: string; ok: false; error: string }
type FileResult = Fixed | Failed

const isFixed = (r: FileResult): r is Fixed => r.ok
const isFailed = (r: FileResult): r is Failed => !r.ok

async function inPool<T, R>(items: T[], size: number, fn: (item: T) => Promise<R>): Promise<R[]> {
  const out: R[] = new Array(items.length)
  let next = 0
  const worker = async () => {
    while (next < items.length) {
      const i = next++
      out[i] = await fn(items[i])
    }
  }
  await Promise.all(Array.from({ length: Math.min(size, items.length) }, worker))
  return out
}

/**
 * Pide al backend los parches de uno o varios hallazgos (una petición por archivo, para que un archivo que
 * falle no frene a los demás), los aplica sobre el borrador de cada archivo y abre el editor en modo diff
 * para revisarlos antes de guardar.
 */
export function useApplyFix(repoId: string) {
  const queryClient = useQueryClient()

  const fixFile = async (file: string, findings: Finding[]): Promise<FileResult> => {
    try {
      const { patches, notes = [] } = await fileApi.fix({ repo_id: repoId, finding_ids: findings.map((f) => f.id) })
      let missed = 0
      for (const path of new Set(patches.map((p) => p.file))) {
        const current = await queryClient.fetchQuery(fileQuery(repoId, path))
        const key = fileKey(repoId, path)
        const store = useEditorStore.getState()
        const result = applyPatches(store.drafts[key] ?? current.content, patches.filter((p) => p.file === path))
        missed += result.missed
        store.applyFix(key, result.content, findings.filter((f) => f.file === path).map((f) => f.id))
      }
      return { file, ok: true, missed, notes }
    } catch (e) {
      return { file, ok: false, error: e instanceof Error ? e.message : String(e) }
    }
  }

  return useMutation({
    mutationFn: async (findings: Finding[]) => {
      if (!findings.length) throw new Error('No hay hallazgos con corrección')
      const byFile = new Map<string, Finding[]>()
      for (const f of findings) byFile.set(f.file, [...(byFile.get(f.file) ?? []), f])
      const results = await inPool([...byFile], CONCURRENCY, ([file, items]) => fixFile(file, items))
      const failed = results.filter(isFailed)
      // Un solo archivo (o todos fallaron): se muestra como error normal
      if (failed.length === results.length) throw new Error(failed.length === 1 ? failed[0].error : `No se pudo corregir ningún archivo. ${failed[0].file}: ${failed[0].error}`)
      return results
    },
    onSuccess: (results) => {
      // El backend re-analiza antes de corregir: hallazgos que ya estaban corregidos quedan resueltos
      void invalidateAnalysis(queryClient)
      const ok = results.filter(isFixed)
      const failed = results.filter(isFailed)
      navigateTo(paths.editor(repoId, { file: ok[0].file, diff: true }))
      if (results.length > 1) {
        const missed = ok.some((r) => r.missed)
        const msg = `Correcciones listas en ${ok.length} de ${results.length} archivos (marcados en el árbol). Revisa el diff y guarda cada uno.`
        const errs = failed.map((r) => `${r.file}: ${r.error}`).join(' · ')
        toast(failed.length || missed ? `${msg} ${missed ? 'Parte no se pudo aplicar porque el código cambió.' : ''} ${errs}`.trim() : msg, { tone: failed.length ? 'err' : 'info' })
        return
      }
      const [r] = ok
      if (r.missed) toast('Parte de la corrección no se pudo aplicar: el código cambió. Revisa el diff.', { tone: 'err' })
      // La IA explica qué cambió y por qué
      else if (r.notes.length) toast(`Propuesta de la IA: ${r.notes.join(' ')} Revisa el diff y guarda.`, { tone: 'info' })
      else toast('Corrección aplicada. Revisa el diff y guarda.', { tone: 'info' })
    },
    onError: (e) => {
      void invalidateAnalysis(queryClient)
      toast(e.message, { tone: 'err' })
    },
  })
}
