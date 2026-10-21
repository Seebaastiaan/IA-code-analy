import { create } from 'zustand'

type Theme = 'light' | 'dark'
const KEY = 'iavoy-theme'

// index.html ya aplicó la clase antes del primer pintado; aquí solo la leemos.
const initial: Theme = document.documentElement.classList.contains('dark') ? 'dark' : 'light'

interface ThemeState {
  theme: Theme
  toggle: () => void
}

export const useTheme = create<ThemeState>((set, get) => ({
  theme: initial,
  toggle: () => {
    const theme: Theme = get().theme === 'dark' ? 'light' : 'dark'
    document.documentElement.classList.toggle('dark', theme === 'dark')
    try {
      localStorage.setItem(KEY, theme)
    } catch {
      /* almacenamiento bloqueado: el tema no se recuerda */
    }
    set({ theme })
  },
}))
