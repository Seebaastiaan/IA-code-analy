import { cn } from '@/shared/utils/cn'
import { Button } from './Button'
import { EmptyState } from './EmptyState'
import { Spinner } from './Spinner'

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-2xl bg-slate-200/70 dark:bg-slate-800/70', className)} />
}

export function PageLoader() {
  return (
    <div className="grid place-items-center py-24 text-slate-400">
      <Spinner className="w-6 h-6" />
    </div>
  )
}

/** Error de carga con reintento. */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <EmptyState icon="alert" title="No se pudo cargar la información">
      <p>{error instanceof Error ? error.message : 'Error desconocido'}</p>
      {onRetry && (
        <Button variant="secondary" className="mt-3" onClick={onRetry}>
          Reintentar
        </Button>
      )}
    </EmptyState>
  )
}
