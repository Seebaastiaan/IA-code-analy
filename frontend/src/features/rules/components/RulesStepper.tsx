import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router'
import { reposApi } from '@/features/repos'
import { toast } from '@/shared/hooks/useToast'
import { paths } from '@/shared/constants/paths'
import { Button, Card, Icon, Spinner } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import { prepareQuery } from '../api/rules.api'
import type { RulePreview } from '../types'
import { currentStep, FLOW_STEPS, nextAction } from '../utils/steps'

/**
 * Los 4 pasos del módulo y la siguiente acción. Se puede saltar a cualquier paso; el paso en curso lo marca el programa.
 * Ningún paso se desmonta (lo escrito en el editor no se pierde): solo se ocultan.
 */
export function RulesStepper({ repoId, rules, step, onStep }: { repoId: string; rules: RulePreview[]; step: number; onStep: (n: number) => void }) {
  const done = currentStep(rules)
  // Mientras «Preparar todo» corre (en el servidor), lo siguiente es esperar, no pulsarlo otra vez
  const prepared = useQuery({ ...prepareQuery(repoId), enabled: false }).data
  const done2 = !prepared?.running && Boolean(prepared?.summary) && done === 2
  const next = prepared?.running
    ? { text: '«Preparar todo» está trabajando: puedes cerrar esta pestaña y volver después.', step: 2, label: 'Ver el avance' }
    : done2
      ? { text: 'Listo: analiza el repositorio de nuevo para ver qué reglas se cumplen.', step: 3, label: 'Ver el resultado' }
      : nextAction(rules)
  return (
    <Card className="p-5">
      <ol className="grid grid-cols-2 lg:grid-cols-4 gap-2" aria-label="Pasos">
        {FLOW_STEPS.map((s, i) => {
          const finished = i < done
          return (
            <li key={s.title}>
              <button
                type="button"
                onClick={() => onStep(i)}
                aria-current={step === i ? 'step' : undefined}
                aria-label={`Paso ${i + 1}: ${s.title}`}
                className={cn(
                  'w-full text-left rounded-xl border p-3 transition',
                  step === i ? 'border-brand-500 bg-brand-50 dark:bg-brand-500/10' : 'border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40',
                )}
              >
                <span className="flex items-center gap-2">
                  <span
                    className={cn(
                      'w-5 h-5 shrink-0 rounded-full grid place-items-center text-[11px] font-bold',
                      finished ? 'bg-emerald-600 text-white' : 'bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300',
                    )}
                  >
                    {finished ? <Icon name="check" className="w-3 h-3" /> : i + 1}
                  </span>
                  <b className="text-sm">{s.title}</b>
                </span>
                <span className="mt-1 block text-xs text-slate-500">{s.text}</span>
              </button>
            </li>
          )
        })}
      </ol>
      <div role="status" className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-50 dark:bg-slate-800/50 px-3.5 py-2.5 text-sm">
        <span>
          <b>Siguiente:</b> {next.text}
        </span>
        {step !== next.step ? (
          <Button onClick={() => onStep(next.step)}>{next.label}</Button>
        ) : step === 2 ? (
          <Button variant="secondary" onClick={() => onStep(3)}>
            Ver el resultado
          </Button>
        ) : null}
      </div>
      <p className="mt-2 text-xs text-slate-400">Las reglas son de este proyecto. Si el repositorio ya tiene un archivo válido, gana el del repositorio.</p>
    </Card>
  )
}

/** Paso 4: el resultado vive en el reporte del último análisis. */
export function ResultStep({ repoId }: { repoId: string }) {
  const navigate = useNavigate()
  const reanalyze = useMutation({
    mutationFn: (id: string) => reposApi.reanalyze(id),
    onSuccess: ({ job_id }) => void navigate(paths.job(job_id)),
    onError: (e) => toast(e.message, { tone: 'err' }),
  })
  return (
    <Card className="p-5">
      <h2 className="font-semibold">Resultado</h2>
      <p className="mt-1 text-sm text-slate-500">
        Cuando las reglas estén aprobadas y preparadas, analiza el repositorio: el reporte dice qué reglas se cumplen, cuáles no y qué corregir.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Link to={paths.report(repoId, 'latest', { tab: 'reglas' })} className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700">
          Ver el último reporte de reglas
        </Link>
        {/* Analiza este mismo repo y lleva al avance (antes abría «Nuevo análisis» vacío y había que volver a elegirlo) */}
        <Button variant="secondary" onClick={() => reanalyze.mutate(repoId)} disabled={reanalyze.isPending}>
          {reanalyze.isPending ? <Spinner className="w-4 h-4" /> : <Icon name="play" className="w-4 h-4" />}
          Analizar de nuevo
        </Button>
      </div>
    </Card>
  )
}
