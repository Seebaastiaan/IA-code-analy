import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from '@/shared/hooks/useToast'
import { Button, Card, Chip, Icon, SeverityBadge, Spinner } from '@/shared/ui'
import { projectRulesQuery, RULES_FILENAME, rulesApi } from '../api/rules.api'
import type { ProjectRules, RuleApproval, RulePreview } from '../types'
import { saveText } from '../utils/rules'

const KIND_LABEL: Record<string, string> = {
  datos: 'Datos',
  flujo: 'Flujo',
  calculo: 'Cálculo',
  permisos: 'Permisos',
  auditoria: 'Auditoría',
  integracion: 'Integración',
  proceso: 'Proceso',
}

const FILTERS = [
  { id: 'todas', label: 'Todas' },
  { id: 'borrador', label: 'Borradores' },
  { id: 'aprobada', label: 'Aprobadas' },
] as const
type Filter = (typeof FILTERS)[number]['id']

const approval = (r: RulePreview): RuleApproval => r.status ?? 'aprobada'

function Row({ rule, open, selected, editable, busy, onToggle, onSelect, onResolve }: {
  rule: RulePreview
  open: boolean
  selected: boolean
  editable: boolean
  busy: boolean
  onToggle: () => void
  onSelect: () => void
  onResolve: (doubt: string) => void
}) {
  const doubts = rule.doubts ?? []
  const scenarios = rule.scenarios ?? []
  return (
    <li className="py-2.5">
      <div className="flex items-center gap-2 min-w-0">
        {editable && (
          <input type="checkbox" checked={selected} onChange={onSelect} aria-label={`Elegir ${rule.id}`} className="shrink-0 accent-brand-600" />
        )}
        <button type="button" onClick={onToggle} aria-expanded={open} aria-label={`${open ? 'Ocultar' : 'Ver'} ${rule.id}`} className="flex flex-1 items-center gap-2 min-w-0 text-left">
          <Icon name="chevron" className={open ? 'w-3.5 h-3.5 shrink-0 rotate-90 transition-transform' : 'w-3.5 h-3.5 shrink-0 transition-transform'} />
          <span className="font-mono text-xs text-slate-500 shrink-0">{rule.id}</span>
          <span className="truncate text-sm">{rule.title}</span>
        </button>
        <span className="hidden sm:flex items-center gap-1.5 shrink-0">
          <SeverityBadge sev={rule.severity} />
          {rule.tipo && <Chip>{KIND_LABEL[rule.tipo] ?? rule.tipo}</Chip>}
          {doubts.length > 0 && <Chip tone="danger">{doubts.length} duda{doubts.length === 1 ? '' : 's'}</Chip>}
          <Chip tone={approval(rule) === 'aprobada' ? 'success' : 'neutral'}>{approval(rule) === 'aprobada' ? 'Aprobada' : 'Borrador'}</Chip>
        </span>
      </div>
      {open && (
        <div className="mt-2 ml-6 space-y-2.5 text-sm text-slate-600 dark:text-slate-300">
          {rule.description && <p>{rule.description}</p>}
          {rule.source && <p className="text-xs text-slate-400">Fuente: {rule.source}</p>}
          {scenarios.length > 0 && (
            <ul className="space-y-1.5">
              {scenarios.map((s, i) => (
                <li key={i} className="rounded-lg bg-slate-50 dark:bg-slate-800/60 px-3 py-2 text-xs leading-relaxed">
                  <b>Dado</b> {s.given} · <b>cuando</b> {s.when} · <b>entonces</b> {s.then}
                </li>
              ))}
            </ul>
          )}
          {doubts.length > 0 && (
            <div>
              <p className="text-xs font-medium text-rose-700 dark:text-rose-300">Dudas abiertas (resuélvelas antes de aprobar)</p>
              <ul className="mt-1 space-y-1">
                {doubts.map((d) => (
                  <li key={d} className="flex items-start gap-2 text-xs">
                    <span className="flex-1">{d}</span>
                    {editable && (
                      <Button variant="ghost" className="shrink-0" disabled={busy} onClick={() => onResolve(d)}>
                        Resuelta
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </li>
  )
}

/** Tabla de aprobación (docs/PROPUESTA_REGLAS_VERIFICABLES.md §5, fase 1): lo importado entra en borrador y solo lo aprobado se verifica. */
export function RulesApprovalTable({ repoId, data }: { repoId: string; data: ProjectRules }) {
  const queryClient = useQueryClient()
  const source = data.active === 'repo' ? data.repo : data.uploaded
  const rules = source?.valid ? source.rules : []
  // Las del repo se editan en su copia de trabajo (no en GitHub): hay que descargar el archivo y hacer commit
  const fromRepo = data.active === 'repo'
  const editable = Boolean(source?.valid)
  const [filter, setFilter] = useState<Filter>('todas')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [openIds, setOpenIds] = useState<Set<string>>(new Set())
  const [messages, setMessages] = useState<string[]>([])

  const done = (saved: ProjectRules) => {
    queryClient.setQueryData(projectRulesQuery(repoId).queryKey, saved)
    setMessages(saved.messages ?? [])
  }
  const states = useMutation({
    mutationFn: ({ ids, status }: { ids: string[]; status: RuleApproval }) => rulesApi.setStates(repoId, ids, status),
    onSuccess: (saved, vars) => {
      done(saved)
      setSelected(new Set())
      if (!(saved.messages ?? []).length) toast(vars.status === 'aprobada' ? 'Reglas aprobadas: se verifican en el siguiente análisis' : 'Reglas devueltas a borrador')
    },
    onError: (e) => toast(e.message, { tone: 'err' }),
  })
  const doubts = useMutation({
    mutationFn: ({ id, list }: { id: string; list: string[] }) => rulesApi.setDoubts(repoId, id, list),
    onSuccess: done,
    onError: (e) => toast(e.message, { tone: 'err' }),
  })

  if (rules.length === 0) return null
  const shown = rules.filter((r) => filter === 'todas' || approval(r) === filter)
  const drafts = rules.filter((r) => approval(r) === 'borrador')
  const ready = drafts.filter((r) => (r.doubts ?? []).length === 0)
  const toggle = (set: Set<string>, id: string) => {
    const next = new Set(set)
    if (!next.delete(id)) next.add(id)
    return next
  }
  const chosen = [...selected].filter((id) => rules.some((r) => r.id === id))
  const busy = states.isPending || doubts.isPending

  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
        <h2 className="font-semibold">Aprobación de las reglas</h2>
        <div role="group" aria-label="Filtrar reglas" className="flex gap-1">
          {FILTERS.map((f) => (
            <Button key={f.id} variant={filter === f.id ? 'secondary' : 'ghost'} aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>
              {f.label}
            </Button>
          ))}
        </div>
      </div>
      <p className="mb-3 text-sm text-slate-500">
        {drafts.length === 0
          ? `Las ${rules.length} reglas están aprobadas.`
          : `${drafts.length} de ${rules.length} reglas son borrador: revísalas, resuelve sus dudas y apruébalas. Solo las aprobadas se verifican.`}
        {fromRepo && editable && ' Son las reglas del repositorio: lo que cambies se guarda en su copia, no en GitHub. Descarga el archivo y haz commit.'}
        {fromRepo && !editable && ' El archivo del repositorio tiene errores: corrígelo para poder aprobar.'}
      </p>
      {messages.length > 0 && (
        <ul role="alert" className="mb-3 rounded-xl bg-amber-50 dark:bg-amber-500/10 text-amber-800 dark:text-amber-200 px-3.5 py-2.5 text-sm space-y-0.5">
          {messages.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      )}
      {shown.length === 0 ? (
        <p className="text-sm text-slate-400 py-4">No hay reglas en este filtro.</p>
      ) : (
        <ul className="divide-y divide-slate-100 dark:divide-slate-800">
          {shown.map((r) => (
            <Row
              key={r.id}
              rule={r}
              open={openIds.has(r.id)}
              selected={selected.has(r.id)}
              editable={editable}
              busy={busy}
              onToggle={() => setOpenIds((s) => toggle(s, r.id))}
              onSelect={() => setSelected((s) => toggle(s, r.id))}
              onResolve={(d) => doubts.mutate({ id: r.id, list: (r.doubts ?? []).filter((x) => x !== d) })}
            />
          ))}
        </ul>
      )}
      {editable && (
        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={() => states.mutate({ ids: chosen, status: 'aprobada' })} disabled={chosen.length === 0 || busy}>
            {states.isPending ? <Spinner className="w-4 h-4" /> : <Icon name="check" className="w-4 h-4" />}
            Aprobar elegidas{chosen.length > 0 ? ` (${chosen.length})` : ''}
          </Button>
          <Button variant="secondary" onClick={() => states.mutate({ ids: ready.map((r) => r.id), status: 'aprobada' })} disabled={ready.length === 0 || busy}>
            Aprobar las que no tienen dudas ({ready.length})
          </Button>
          <Button variant="ghost" onClick={() => states.mutate({ ids: chosen, status: 'borrador' })} disabled={chosen.length === 0 || busy}>
            Volver a borrador
          </Button>
          {fromRepo && data.repo && (
            <Button variant="ghost" onClick={() => saveText(RULES_FILENAME, data.repo?.content ?? '')}>
              <Icon name="download" className="w-4 h-4" />
              Descargar para el repo
            </Button>
          )}
        </div>
      )}
    </Card>
  )
}
