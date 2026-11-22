import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from '@/shared/hooks/useToast'
import { Card, Chip, Spinner } from '@/shared/ui'
import { concordanceQuery, rulesApi } from '../api/rules.api'
import type { ControlExpected, ControlItem } from '../types'
import { concordanceText, LIGHT, lightOf } from '../utils/rules'

const OUTCOME = {
  acerto: { label: 'Acertó', tone: 'success' },
  fallo: { label: 'Falló', tone: 'danger' },
  sin_resultado: { label: 'Sin resultado', tone: 'neutral' },
} as const
const CONFIDENCE: Record<string, string> = { alta: 'Confianza alta', media: 'Confianza media', baja: 'Confianza baja', ninguna: 'Sin comprobar' }

/**
 * Casos de control (docs/PLAN_REGLAS_AUTOMATICO.md, paso 6): lo que el equipo ya sabe de algunas reglas. No cambia ningún
 * resultado: sirve para saber si se le puede creer al programa.
 */
export function ConcordanceCard({ repoId, version }: { repoId: string; version: string }) {
  const queryClient = useQueryClient()
  const { data } = useQuery(concordanceQuery(repoId, version))
  const set = useMutation({
    mutationFn: ({ id, expected }: { id: string; expected: ControlExpected | null }) => rulesApi.setExpected(repoId, id, expected),
    onSuccess: (saved) => queryClient.setQueryData(concordanceQuery(repoId, version).queryKey, saved),
    onError: (e) => toast(e.message, { tone: 'err' }),
  })
  if (!data || data.items.length === 0) return null

  const row = (i: ControlItem) => (
    <li key={i.rule_id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
      <span className="font-mono text-xs text-slate-500 shrink-0">{i.rule_id}</span>
      <span className="flex-1 min-w-40 truncate" title={i.title}>{i.title}</span>
      <select
        aria-label={`Lo que sabes de ${i.rule_id}`}
        value={i.expected ?? ''}
        disabled={set.isPending}
        onChange={(e) => set.mutate({ id: i.rule_id, expected: (e.target.value || null) as ControlExpected | null })}
        className="rounded-lg border border-slate-200 dark:border-slate-700 bg-transparent px-2 py-1 text-xs"
      >
        <option value="">No sé</option>
        <option value="cumple">Sé que se cumple</option>
        <option value="viola">Sé que se viola</option>
      </select>
      {i.outcome && <Chip tone={OUTCOME[i.outcome].tone}>{OUTCOME[i.outcome].label}</Chip>}
      {i.status && (
        <span className="text-xs text-slate-500" title={i.confidence ? CONFIDENCE[i.confidence] : undefined}>
          {LIGHT[lightOf(i.status)].dot} {i.confidence ? CONFIDENCE[i.confidence] : ''}
        </span>
      )}
    </li>
  )

  return (
    <Card className="p-5 sm:p-6">
      <div className="flex items-center gap-2">
        <h2 className="font-semibold">¿Se le puede creer al programa?</h2>
        {set.isPending && <Spinner className="w-4 h-4" />}
      </div>
      <p className="mt-1 text-sm text-slate-500">
        Opcional. De las reglas que ya conoces, di si se cumplen o se violan en tu código: no cambia ningún resultado, solo se compara con lo que el programa
        encontró{data.report_num ? ` en el último análisis` : ' cuando haya un análisis'}.
      </p>
      <p className="mt-2 text-sm font-medium" role="status">
        {concordanceText(data.known, data.hits, data.misses, data.unverified)}
      </p>
      <ul className="mt-2 divide-y divide-slate-100 dark:divide-slate-800">{data.items.map(row)}</ul>
    </Card>
  )
}
