import { useEffect, type ReactNode } from 'react'
import { cn } from '@/shared/utils/cn'
import { cardClass } from './styles'

/** Cierra con Escape y bloquea el scroll del body mientras está abierto. */
function useOverlayBehavior(onClose: () => void) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [onClose])
}

export function Drawer({ onClose, children }: { onClose: () => void; children: ReactNode }) {
  useOverlayBehavior(onClose)
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={onClose} />
      <aside role="dialog" aria-modal="true" className="animate-slide-in relative w-full sm:w-[30rem] h-full bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 shadow-2xl flex flex-col">
        {children}
      </aside>
    </div>
  )
}

export function Modal({ onClose, className, children }: { onClose: () => void; className?: string; children: ReactNode }) {
  useOverlayBehavior(onClose)
  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4">
      <div className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm" onClick={onClose} />
      <div role="dialog" aria-modal="true" className={cn('animate-fade-in relative w-full max-w-lg shadow-2xl max-h-[90vh] overflow-y-auto scroll-thin', cardClass, className)}>
        {children}
      </div>
    </div>
  )
}
