import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from '@/shared/hooks/useToast'
import { Button, Card, Chip, Spinner } from '@/shared/ui'
import { projectRulesQuery, rulesApi } from '../api/rules.api'
import type { ContradictionSide, ProjectRules } from '../types'

function Side({ side }: { side: ContradictionSide }) {
  return (
    <div className="min-w-0 flex-1 rounded-xl border border-slate-200 dark:border-slate-800 p-3.5">
      <p className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
        <span className="font-mono">{side.id}</span>
        {side.source && <span>{side.source}</span>}
      </p>
      <p className="mt-1 font-medium">{side.title}</p>
      {side.description && <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{side.description}</p>}
    </div>
  )
}

/**
 * El documento dice dos cosas que no pueden ser ciertas a la vez: se pregunta cuál vale, una por una y con botones.
 * La regla que no vale se quita; «Las dos valen» solo quita la marca. Sin tocar el archivo de reglas.
 */
export function ContradictionsCard({ repoId, data }: { repoId: string; data: ProjectRules }) {
  const queryClient = useQueryClient()
  const pending = data.contradictions ?? []
  const choose = useMutation({
    mutationFn: ({ a, b, keep }: { a: string; b: string; keep: string }) => rulesApi.resolveContradiction(repoId, a, b, keep),
    onSuccess: (next) => {
      queryClient.setQueryData(projectRulesQuery(repoId).queryKey, next)
      if (!next.contradictions?.length) toast('Listo: el documento ya no se contradice. Sigue con las preguntas.')
    },
    onError: (e) => toast(e.message, { tone: 'err' }),
  })
  if (!pending.length) return null
  const c = pending[0]
  const busy = (keep: string) => choose.isPending && choose.variables?.keep === keep
  const pick = (keep: string) => choose.mutate({ a: c.a.id, b: c.b.id, keep })

  return (
    <Card className="p-5 sm:p-6" aria-label="El documento se contradice">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
        <h2 className="font-semibold">El documento se contradice: ¿cuál vale?</h2>
        <Chip tone="danger">
          {pending.length === 1 ? 'Falta 1' : `Faltan ${pending.length}`}
        </Chip>
      </div>
      <p className="text-sm text-slate-500 mb-3">
        Estas dos reglas no pueden cumplirse a la vez{c.reason ? `: ${c.reason.replace(/[.\s]+$/, '')}.` : '.'} La que elijas se queda y la otra se quita.
      </p>
      <div className="flex flex-col sm:flex-row gap-3">
        <Side side={c.a} />
        <Side side={c.b} />
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button onClick={() => pick(c.a.id)} disabled={choose.isPending}>
          {busy(c.a.id) && <Spinner className="w-4 h-4" />}
          Vale {c.a.id}
        </Button>
        <Button onClick={() => pick(c.b.id)} disabled={choose.isPending}>
          {busy(c.b.id) && <Spinner className="w-4 h-4" />}
          Vale {c.b.id}
        </Button>
        <Button variant="ghost" onClick={() => pick('ambas')} disabled={choose.isPending}>
          {busy('ambas') && <Spinner className="w-4 h-4" />}
          Las dos valen (no se contradicen)
        </Button>
      </div>
    </Card>
  )
}
