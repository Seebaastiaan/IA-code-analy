import { useToastStore } from '@/shared/hooks/useToast'
import { Toast } from '@/shared/ui'

export function Toaster() {
  const { toasts, dismiss } = useToastStore()
  return (
    <div className="fixed z-[60] bottom-4 right-4 left-4 sm:left-auto sm:w-96 space-y-2" aria-live="polite">
      {toasts.map((t) => (
        <Toast key={t.id} toast={t} onClose={() => dismiss(t.id)} />
      ))}
    </div>
  )
}
