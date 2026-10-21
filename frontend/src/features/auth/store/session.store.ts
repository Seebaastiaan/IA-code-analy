import { create } from 'zustand'
import type { User } from '../types'

const KEY = 'iavoy-token'

/** "Mantener sesión iniciada" guarda el token en localStorage; si no, solo dura la pestaña. */
function readToken(): string | null {
  try {
    return localStorage.getItem(KEY) ?? sessionStorage.getItem(KEY)
  } catch {
    return null
  }
}

function writeToken(token: string | null, remember = true) {
  try {
    localStorage.removeItem(KEY)
    sessionStorage.removeItem(KEY)
    if (token) (remember ? localStorage : sessionStorage).setItem(KEY, token)
  } catch {
    /* almacenamiento bloqueado: la sesión vive solo en memoria */
  }
}

interface SessionState {
  token: string | null
  user: User | null
  signIn: (token: string, user: User, remember: boolean) => void
  setUser: (user: User) => void
  signOut: () => void
}

export const useSession = create<SessionState>((set) => ({
  token: readToken(),
  user: null,
  signIn: (token, user, remember) => {
    writeToken(token, remember)
    set({ token, user })
  },
  setUser: (user) => set({ user }),
  signOut: () => {
    writeToken(null)
    set({ token: null, user: null })
  },
}))
