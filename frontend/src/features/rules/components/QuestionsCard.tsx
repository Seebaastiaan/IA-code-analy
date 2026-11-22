import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from '@/shared/hooks/useToast'
import { Button, Card, Chip, Icon } from '@/shared/ui'
import { projectRulesQuery, rulesApi } from '../api/rules.api'
import type { DoubtAnswer, ProjectRules } from '../types'
import { parseDoubt } from '../utils/rules'
import { pendingQuestions, type Question } from '../utils/steps'

/**
 * Preguntas para ti: una por una, con la frase del documento al lado y lo que cambia según la respuesta.
 * Responder la guarda en la regla (el programa la recuerda) y pasa a la siguiente.
 */
export function QuestionsCard({ repoId, data }: { repoId: string; data: ProjectRules }) {
  const queryClient = useQueryClient()
  const source = data.active === 'repo' ? data.repo : data.uploaded
  const rules = source?.valid ? source.rules : []
  const questions = pendingQuestions(rules)
  const [index, setIndex] = useState(0)
  const [written, setWritten] = useState('')

  const saved = (next: ProjectRules) => queryClient.setQueryData(projectRulesQuery(repoId).queryKey, next)
  const answer = useMutation({
    mutationFn: ({ q, value }: { q: Question; value: DoubtAnswer | string }) => rulesApi.answerDoubt(repoId, q.rule.id, q.doubt, value),
    onSuccess: (next) => {
      saved(next)
      setWritten('')
    },
    onError: (e) => toast(e.message, { tone: 'err' }),
  })
  const close = useMutation({
    mutationFn: (q: Question) => rulesApi.setDoubts(repoId, q.rule.id, (q.rule.doubts ?? []).filter((d) => d !== q.doubt)),
    onSuccess: saved,
    onError: (e) => toast(e.message, { tone: 'err' }),
  })

  if (!source?.valid || rules.length === 0) return null
  if (questions.length === 0)
    return (
      <Card className="p-5" aria-label="Preguntas para ti">
        <p className="flex items-center gap-2 text-sm font-medium text-emerald-700 dark:text-emerald-300">
          <Icon name="check" className="w-4 h-4" />
          No tienes preguntas pendientes.
        </p>
      </Card>
    )

  const at = Math.min(index, questions.length - 1)
  const q = questions[at]
  const { question, yes, no } = parseDoubt(q.doubt)
  const busy = answer.isPending || close.isPending

  return (
    <Card className="p-5 sm:p-6" aria-label="Preguntas para ti">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">Preguntas para ti</h2>
        <div className="flex items-center gap-1 text-sm text-slate-500">
          <Button variant="ghost" aria-label="Pregunta anterior" disabled={at === 0} onClick={() => setIndex(at - 1)}>
            ←
          </Button>
          <span>
            Pregunta {at + 1} de {questions.length}
          </span>
          <Button variant="ghost" aria-label="Pregunta siguiente" disabled={at >= questions.length - 1} onClick={() => setIndex(at + 1)}>
            →
          </Button>
        </div>
      </div>
      <p className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <span className="font-mono">{q.rule.id}</span>
        <span className="font-medium text-slate-700 dark:text-slate-200">{q.rule.title}</span>
        {q.rule.source && <Chip>{q.rule.source}</Chip>}
      </p>
      <p className="mt-2 text-base font-medium">{question}</p>
      {q.rule.quote && (
        <blockquote className="mt-3 border-l-2 border-slate-300 dark:border-slate-600 pl-3 text-sm italic text-slate-600 dark:text-slate-300">
          «{q.rule.quote}»
          <span className="block not-italic text-xs text-slate-400">Lo que dice el documento</span>
        </blockquote>
      )}
      <div className="mt-4 grid sm:grid-cols-2 gap-3">
        {([
          ['si', 'Sí', yes],
          ['no', 'No', no],
        ] as const).map(([value, label, effect]) => (
          <div key={value} className="rounded-xl border border-slate-200 dark:border-slate-800 p-3.5">
            <Button disabled={busy} onClick={() => answer.mutate({ q, value })} aria-label={`Responder ${label.toLowerCase()}: ${q.doubt}`}>
              {label}
            </Button>
            <p className="mt-2 text-xs text-slate-500">
              {effect ? (
                <>
                  <b>Si dices {label}:</b> {effect}
                </>
              ) : (
                `Si dices ${label}, la regla anota tu respuesta y las pruebas la usarán.`
              )}
            </p>
          </div>
        ))}
      </div>
      {yes === null && (
        <div className="mt-3 rounded-xl border border-slate-200 dark:border-slate-800 p-3.5">
          <label className="text-sm font-medium" htmlFor="respuesta-escrita">
            O escribe tu respuesta
          </label>
          <textarea
            id="respuesta-escrita"
            value={written}
            onChange={(e) => setWritten(e.target.value)}
            maxLength={300}
            rows={2}
            placeholder="Por ejemplo: cuenta con IVA del 16%"
            className="mt-1.5 w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-transparent p-2 text-sm outline-none focus:border-brand-500"
          />
          <Button className="mt-2" variant="secondary" disabled={busy || !written.trim()} onClick={() => answer.mutate({ q, value: written.trim() })}>
            Guardar mi respuesta
          </Button>
        </div>
      )}
      <p className="mt-3 text-xs text-slate-400">
        El programa recuerda tu respuesta para próximas importaciones.{' '}
        <button type="button" className="underline" disabled={busy} onClick={() => close.mutate(q)}>
          Cerrar sin responder
        </button>
      </p>
    </Card>
  )
}
