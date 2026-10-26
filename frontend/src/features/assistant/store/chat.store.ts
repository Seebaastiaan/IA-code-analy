import { create } from 'zustand'
import type { ChatMessage } from '../types'

let seq = 0

interface ChatState {
  /** Conversación por repositorio (se conserva al navegar entre pantallas) */
  byRepo: Record<string, ChatMessage[]>
  /** Agrega un mensaje y devuelve su id */
  add: (repoId: string, msg: Omit<ChatMessage, 'id'>) => number
  /** Cambia un mensaje existente (la respuesta que llega por streaming) */
  update: (repoId: string, id: number, patch: Partial<Omit<ChatMessage, 'id'>> | ((m: ChatMessage) => Partial<ChatMessage>)) => void
}

export const useChatStore = create<ChatState>((set) => ({
  byRepo: {},
  add: (repoId, msg) => {
    const id = ++seq
    set((s) => ({ byRepo: { ...s.byRepo, [repoId]: [...(s.byRepo[repoId] ?? []), { ...msg, id }] } }))
    return id
  },
  update: (repoId, id, patch) =>
    set((s) => ({
      byRepo: {
        ...s.byRepo,
        [repoId]: (s.byRepo[repoId] ?? []).map((m) => (m.id === id ? { ...m, ...(typeof patch === 'function' ? patch(m) : patch) } : m)),
      },
    })),
}))
