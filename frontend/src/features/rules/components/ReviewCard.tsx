import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from '@/shared/hooks/useToast'
import { Button, Card, Chip, Icon, Spinner } from '@/shared/ui'
import { ruleTestsQuery, rulesApi, useRuleTests } from '../api/rules.api'
import { brokenCount, reviewItems, type ReviewItem } from '../utils/review'

function Item({ item, onApprove, busy }: { item: ReviewItem; onApprove: () => void; busy: boolean }) {
  const [open, setOpen] = useState(false)
  const { row } = item
  return (
    <li className="py-3 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 max-w-xl">
          <p className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-mono text-xs text-slate-500">{row.id}</span>
            <span className="font-medium">{row.title}</span>
          </p>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm">
            <Chip tone={item.passes ? 'success' : 'danger'}>{item.passes ? 'Su prueba dice: se cumple' : 'Su prueba dice: no se cumple'}</Chip>
          </p>
          <p className="mt-1 text-xs text-slate-500">{item.advice}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => setOpen(!open)} aria-expanded={open}>
            {open ? 'Ocultar' : '¿Por qué?'}
          </Button>
          <Button variant={item.recommended ? 'primary' : 'secondary'} onClick={onApprove} disabled={busy || Boolean(row.test?.blocked)} title={row.test?.blocked ?? undefined}>
            <Icon name="check" className="w-4 h-4" />
            Aprobar
          </Button>
        </div>
      </div>
      {open && (
        <ul className="mt-2 space-y-1 text-xs text-slate-600 dark:text-slate-300 list-disc pl-5">
          {item.why.map((w) => (
            <li key={w}>{w}</li>
          ))}
          {item.failure && (
            <li>
              Lo que falló: <span className="font-mono">{item.failure}</span>
            </li>
          )}
          {row.crosscheck.note && <li>{row.crosscheck.note}</li>}
        </ul>
      )}
    </li>
  )
}

/**
 * Lo que «Preparar todo» no aprobó solo, una regla por fila: qué dice su prueba, qué conviene hacer y «Aprobar» en un
 * clic. El detalle técnico (código, prueba de fuerza) queda en las herramientas avanzadas.
 */
export function ReviewCard({ repoId }: { repoId: string }) {
  const queryClient = useQueryClient()
  const { data } = useRuleTests(repoId)
  const approve = useMutation({
    mutationFn: (ids: string[]) => rulesApi.approveTests(repoId, ids),
    onSuccess: (view, ids) => {
      queryClient.setQueryData(ruleTestsQuery(repoId).queryKey, view)
      toast(ids.length === 1 ? `${ids[0]} aprobada: cuenta desde el siguiente análisis` : 'Pruebas aprobadas: cuentan desde el siguiente análisis')
    },
    onError: (e) => toast(e.message, { tone: 'err' }),
  })
  const items = reviewItems(data)
  const broken = brokenCount(data)
  if (data?.busy || (!items.length && !broken)) return null
  const recommended = items.filter((i) => i.recommended && !i.row.test?.blocked).map((i) => i.row.id)

  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
        <div className="max-w-xl">
          <h2 className="font-semibold">Esperan tu revisión ({items.length})</h2>
          <p className="mt-1 text-sm text-slate-500">El programa no las aprobó solo porque algún control no pasó. Solo cuentan en el análisis las que apruebes.</p>
        </div>
        {recommended.length > 1 && (
          <Button variant="secondary" onClick={() => approve.mutate(recommended)} disabled={approve.isPending}>
            {approve.isPending ? <Spinner className="w-4 h-4" /> : <Icon name="check" className="w-4 h-4" />}
            Aprobar las recomendadas ({recommended.length})
          </Button>
        )}
      </div>
      {items.length > 0 && (
        <ul className="divide-y divide-slate-100 dark:divide-slate-800">
          {items.map((item) => (
            <Item key={item.row.id} item={item} busy={approve.isPending} onApprove={() => approve.mutate([item.row.id])} />
          ))}
        </ul>
      )}
      {broken > 0 && (
        <p className="mt-3 text-xs text-slate-500">
          {broken === 1 ? '1 prueba no pudo preparar su caso' : `${broken} pruebas no pudieron preparar su caso`} (no es culpa del código): «Volver a preparar» las escribe de nuevo.
        </p>
      )}
    </Card>
  )
}
