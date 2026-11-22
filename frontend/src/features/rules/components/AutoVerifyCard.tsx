import { Button, Card, Icon, Spinner } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import { useAutoVerify, type AutoStatus } from '../hooks/useAutoVerify'

function StepIcon({ status }: { status: AutoStatus }) {
  if (status === 'haciendo') return <Spinner className="w-4 h-4 text-brand-600" />
  if (status === 'hecho') return <Icon name="check" className="w-4 h-4 text-emerald-600" />
  if (status === 'fallo') return <Icon name="alert" className="w-4 h-4 text-rose-600" />
  return <span className="w-2 h-2 rounded-full bg-slate-300 dark:bg-slate-600" />
}

/**
 * «Preparar todo» (docs/PLAN_REGLAS_AUTOMATICO.md): un botón que hace lo técnico. El equipo solo decide lo que el
 * programa no puede decidir solo (reglas con dudas, errores que explica en una frase).
 */
export function AutoVerifyCard({ repoId }: { repoId: string }) {
  const { steps, running, summary, run, stop } = useAutoVerify(repoId)
  const started = steps.some((s) => s.status !== 'pendiente')
  const failed = steps.some((s) => s.status === 'fallo')

  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-xl">
          <h2 className="font-semibold">Preparar todo para verificar las reglas</h2>
          <p className="mt-1 text-sm text-slate-500">
            El programa aprueba las reglas sin dudas, prepara el entorno, escribe y ejecuta una prueba por regla y comprueba que detecten fallos. Solo te pide decidir lo que no puede resolver solo.
          </p>
          <p className="mt-1 text-xs text-slate-400">Puede tardar de 3 a 8 minutos. Sigue aunque cierres esta pestaña. Si la IA está saturada, reintenta en un rato: lo ya hecho se conserva.</p>
        </div>
        {running ? (
          <Button variant="secondary" onClick={() => void stop()}>
            Detener
          </Button>
        ) : (
          <Button onClick={() => void run()}>
            <Icon name="bolt" className="w-4 h-4" />
            {started ? (failed ? 'Reintentar' : 'Volver a preparar') : 'Preparar todo'}
          </Button>
        )}
      </div>
      {started && (
        <ol className="mt-4 space-y-2" aria-label="Avance de la preparación">
          {steps.map((s) => (
            <li key={s.id} className="flex items-start gap-2.5 text-sm">
              <span className="mt-1 w-4 h-4 grid place-items-center shrink-0">
                <StepIcon status={s.status} />
              </span>
              <span>
                <span className={cn(s.status === 'pendiente' ? 'text-slate-400' : 'text-slate-700 dark:text-slate-200')}>{s.label}</span>
                {s.note && <span className={cn('block text-xs', s.status === 'fallo' ? 'text-rose-600 dark:text-rose-400' : 'text-slate-500')}>{s.note}</span>}
              </span>
            </li>
          ))}
        </ol>
      )}
      {summary && <p className="mt-3 text-sm font-medium text-emerald-700 dark:text-emerald-300">{summary}</p>}
    </Card>
  )
}
