import { Link } from 'react-router'
import { paths } from '@/shared/constants/paths'
import { Button, Card, Icon } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import type { RulePreview } from '../types'

export const FLOW_STEPS = [
  { title: 'Importar', text: 'Sube el documento de requisitos y la IA saca las reglas.' },
  { title: 'Preguntas y aprobación', text: 'Contesta Sí o No a lo ambiguo y aprueba las reglas. Solo lo aprobado se verifica.' },
  { title: 'Preparar todo', text: 'El programa prepara el entorno, escribe las pruebas y las corre.' },
  { title: 'Resultado', text: 'Analiza el repositorio y mira qué reglas se cumplen.' },
] as const

const isDraft = (r: RulePreview) => (r.status ?? 'aprobada') === 'borrador'

/** Paso en el que está el proyecto según sus reglas: sin reglas → 0; con borradores → 1; todo aprobado → 2. */
export function currentStep(rules: RulePreview[]): number {
  if (!rules.length) return 0
  return rules.some(isDraft) ? 1 : 2
}

/** Lo que el programa recomienda hacer ahora, en una frase y con el paso al que lleva. */
export function nextAction(rules: RulePreview[]): { text: string; step: number; label: string } {
  if (!rules.length) return { text: 'Empieza importando el documento de requisitos del proyecto.', step: 0, label: 'Importar' }
  const drafts = rules.filter(isDraft)
  if (drafts.length) {
    const asking = drafts.filter((r) => (r.doubts ?? []).length > 0).length
    const text =
      asking > 0
        ? `Tienes ${asking} regla${asking === 1 ? '' : 's'} con preguntas por contestar y ${drafts.length} en borrador.`
        : `Tienes ${drafts.length} regla${drafts.length === 1 ? '' : 's'} en borrador por aprobar.`
    return { text, step: 1, label: 'Revisar las reglas' }
  }
  return { text: 'Todas las reglas están aprobadas: ya puedes pulsar «Preparar todo».', step: 2, label: 'Ir a «Preparar todo»' }
}

/**
 * Los 4 pasos del módulo y la siguiente acción. Se puede saltar a cualquier paso; el paso en curso lo marca el programa.
 * Ningún paso se desmonta (lo escrito en el editor no se pierde): solo se ocultan.
 */
export function RulesStepper({ rules, step, onStep }: { rules: RulePreview[]; step: number; onStep: (n: number) => void }) {
  const done = currentStep(rules)
  const next = nextAction(rules)
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
        <Link to={paths.analyze()} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 dark:border-slate-700 px-4 py-2 text-sm font-medium hover:bg-slate-50 dark:hover:bg-slate-800/40">
          Analizar de nuevo
        </Link>
      </div>
    </Card>
  )
}
