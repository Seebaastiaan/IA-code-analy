import type { ReactNode } from 'react'
import { cn } from '@/shared/utils/cn'
import { Icon } from './Icon'

export type ToastTone = 'ok' | 'err' | 'info'

export interface ToastData {
  id: number
  message: ReactNode
  tone: ToastTone
  action?: { label: string; onClick: () => void }
}

const TONE_ICON = {
  ok: { icon: 'check', cls: 'bg-emerald-100 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400' },
  err: { icon: 'alert', cls: 'bg-rose-100 text-rose-600 dark:bg-rose-500/15 dark:text-rose-400' },
  info: { icon: 'bolt', cls: 'bg-brand-100 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300' },
} as const

export function Toast({ toast, onClose }: { toast: ToastData; onClose: () => void }) {
  const t = TONE_ICON[toast.tone]
  return (
    <div role="status" className="animate-fade-in flex items-center gap-3 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl p-3 pr-2">
      <span className={cn('w-8 h-8 shrink-0 rounded-lg grid place-items-center', t.cls)}>
        <Icon name={t.icon} className="w-4 h-4" />
      </span>
      <p className="text-sm flex-1">{toast.message}</p>
      {toast.action && (
        <button
          type="button"
          onClick={() => {
            toast.action!.onClick()
            onClose()
          }}
          className="inline-flex items-center rounded-lg text-sm font-medium px-2.5 py-1.5 text-brand-600 dark:text-brand-300 hover:bg-slate-100 dark:hover:bg-slate-800"
        >
          {toast.action.label}
        </button>
      )}
      <button type="button" onClick={onClose} aria-label="Cerrar" className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800">
        <Icon name="x" className="w-4 h-4" />
      </button>
    </div>
  )
}
