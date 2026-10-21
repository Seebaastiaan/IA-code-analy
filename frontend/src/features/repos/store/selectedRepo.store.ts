import { create } from 'zustand'

const KEY = 'iavoy-repo'

function read(): string | null {
  try {
    return localStorage.getItem(KEY)
  } catch {
    return null
  }
}

interface SelectedRepoState {
  /** Repo activo: lo usan el tablero y los enlaces del sidebar (Reporte, Editor, Asistente…) */
  repoId: string | null
  select: (id: string) => void
}

export const useSelectedRepo = create<SelectedRepoState>((set) => ({
  repoId: read(),
  select: (repoId) => {
    try {
      localStorage.setItem(KEY, repoId)
    } catch {
      /* sin almacenamiento: se recuerda solo en memoria */
    }
    set({ repoId })
  },
}))
