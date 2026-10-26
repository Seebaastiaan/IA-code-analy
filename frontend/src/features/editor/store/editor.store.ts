import { create } from 'zustand'

export const fileKey = (repoId: string, path: string) => `${repoId}:${path}`

interface EditorState {
  /** Borradores sin guardar por archivo (clave repo:ruta) */
  drafts: Record<string, string>
  /** Hallazgos con fix aplicado en el borrador, aún sin guardar */
  pending: Record<string, number[]>
  setDraft: (key: string, content: string) => void
  applyFix: (key: string, content: string, findingIds: number[]) => void
  discard: (key: string) => void
}

export const useEditorStore = create<EditorState>((set) => ({
  drafts: {},
  pending: {},
  setDraft: (key, content) => set((s) => ({ drafts: { ...s.drafts, [key]: content } })),
  applyFix: (key, content, ids) =>
    set((s) => ({
      drafts: { ...s.drafts, [key]: content },
      pending: { ...s.pending, [key]: [...new Set([...(s.pending[key] ?? []), ...ids])] },
    })),
  discard: (key) =>
    set((s) => {
      const drafts = { ...s.drafts }
      const pending = { ...s.pending }
      delete drafts[key]
      delete pending[key]
      return { drafts, pending }
    }),
}))
