import type { ReactNode } from 'react'
import { create } from 'zustand'
import type { ToastData, ToastTone } from '@/shared/ui/Toast'

interface ToastOptions {
  tone?: ToastTone
  action?: ToastData['action']
  /** Duración en ms (por defecto 4500) */
  ms?: number
}

interface ToastState {
  toasts: ToastData[]
  push: (message: ReactNode, opts?: ToastOptions) => void
  dismiss: (id: number) => void
}

let nextId = 0

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  push: (message, { tone = 'ok', action, ms = 4500 } = {}) => {
    const id = ++nextId
    set({ toasts: [...get().toasts, { id, message, tone, action }] })
    setTimeout(() => get().dismiss(id), ms)
  },
  dismiss: (id) => set({ toasts: get().toasts.filter((t) => t.id !== id) }),
}))

/** Atajo para lanzar toasts fuera de componentes (p. ej. en mutaciones). */
export const toast = (message: ReactNode, opts?: ToastOptions) => useToastStore.getState().push(message, opts)
