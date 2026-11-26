import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from '@/shared/hooks/useToast'
import { Button, Card, Chip, Icon, SeverityBadge, Spinner } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import { projectRulesQuery, RULES_FILENAME, rulesApi } from '../api/rules.api'
import type { DoubtAnswer, ProjectRules, RuleApproval, RulePreview } from '../types'
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
  { id: 'decision', label: 'Necesitan mi decisión' },
  { id: 'borrador', label: 'Borradores' },
  { id: 'aprobada', label: 'Aprobadas' },
] as const
type Filter = (typeof FILTERS)[number]['id']

/** Mismo texto sin importar mayúsculas, espacios ni el punto final (la IA a veces repite el título como descripción). */
const norm = (t: string) => t.trim().replace(/[.\s]+$/, '').replace(/\s+/g, ' ').toLowerCase()
const sameText = (a: string, b: string) => norm(a) === norm(b)

const approval = (r: RulePreview): RuleApproval => r.status ?? 'aprobada'

function Row({ rule, open, selected, editable, busy, onToggle, onSelect, onResolve, onAnswer, onRevert }: {
  rule: RulePreview
  open: boolean
  selected: boolean
  editable: boolean
  busy: boolean
  onToggle: () => void
  onSelect: () => void
  onResolve: (doubt: string) => void
  onAnswer: (doubt: string, answer: DoubtAnswer) => void
  onRevert: () => void
}) {
  const doubts = rule.doubts ?? []
  const scenarios = rule.scenarios ?? []
  return (
    <li className="py-2.5">
      <div className="flex items-center gap-2 min-w-0">
        {editable && (
          <input type="checkbox" checked={selected} onChange={onSelect} aria-label={`Elegir ${rule.id}`} className="shrink-0 accent-brand-600" />
        )}
        <button type="button" onClick={onToggle} aria-expanded={open} aria-label={`${open ? 'Ocultar' : 'Ver'} ${rule.id}`} className="flex flex-1 items-start gap-2 min-w-0 text-left">
          <Icon name="chevron" className={open ? 'w-3.5 h-3.5 shrink-0 rotate-90 transition-transform' : 'w-3.5 h-3.5 shrink-0 transition-transform'} />
          <span className="font-mono text-xs text-slate-500 shrink-0">{rule.id}</span>
          <span className="text-sm break-words min-w-0">{rule.title}</span>
          {rule.source && <span className="hidden md:inline shrink-0 max-w-[14rem] truncate text-xs text-slate-400" title={rule.source}>{rule.source}</span>}
        </button>
        <span className="hidden sm:flex items-center gap-1.5 shrink-0">
          <SeverityBadge sev={rule.severity} />
          {rule.tipo && <Chip>{KIND_LABEL[rule.tipo] ?? rule.tipo}</Chip>}
          {doubts.length > 0 && <Chip tone="danger">{doubts.length} duda{doubts.length === 1 ? '' : 's'}</Chip>}
          <Chip tone={approval(rule) === 'aprobada' ? 'success' : 'neutral'} title={approval(rule) === 'aprobada' ? 'Aprobada: se verifica en el análisis' : 'Borrador: todavía no se verifica; apruébala cuando no tenga dudas'}>{approval(rule) === 'aprobada' ? (rule.approved_by === 'programa' ? 'Aprobada por el programa' : 'Aprobada') : 'Borrador'}</Chip>
        </span>
      </div>
      {open && (
        <div className="mt-2 ml-6 space-y-2.5 text-sm text-slate-600 dark:text-slate-300">
          {rule.description && !sameText(rule.description, rule.title) && <p>{rule.description}</p>}
          {rule.source && <p className="text-xs text-slate-400">Fuente: {rule.source}</p>}
          {rule.approved_by === 'programa' && approval(rule) === 'aprobada' && (
            <p className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
              La aprobó el programa: cumplía todas las condiciones (sin dudas y con la cita en el documento).
              {editable && (
                <Button variant="ghost" disabled={busy} onClick={onRevert}>
                  Revertir a borrador
                </Button>
              )}
            </p>
          )}
          {rule.quote && (
            <blockquote className="border-l-2 border-slate-300 dark:border-slate-600 pl-3 text-xs italic text-slate-500">
              «{rule.quote}»
              <span className={cn('not-italic ml-2 font-medium', rule.quote_ok === false ? 'text-rose-600 dark:text-rose-400' : rule.quote_ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400')}>
                {rule.quote_ok === false ? '⚠ No está en el documento' : rule.quote_ok ? '✓ Comprobada en el documento' : 'Sin comprobar'}
              </span>
            </blockquote>
          )}
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
              <p className="text-sm font-medium">Preguntas para ti: contesta Sí o No (el programa recuerda la respuesta)</p>
              <ul className="mt-1 space-y-1">
                {doubts.map((d) => (
                  <li key={d} className="flex flex-wrap items-start gap-2 text-sm">
                    <span className="flex-1 min-w-48">{d}</span>
                    {editable && (
                      <span className="flex shrink-0 gap-1">
                        <Button variant="secondary" disabled={busy} onClick={() => onAnswer(d, 'si')} aria-label={`Responder sí: ${d}`}>
                          Sí
                        </Button>
                        <Button variant="secondary" disabled={busy} onClick={() => onAnswer(d, 'no')} aria-label={`Responder no: ${d}`}>
                          No
                        </Button>
                        <Button variant="ghost" disabled={busy} onClick={() => onResolve(d)} title="Cerrar la pregunta sin guardar una respuesta">
                          Cerrar sin responder
                        </Button>
                      </span>
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

  const answer = useMutation({
    mutationFn: ({ id, doubt, value }: { id: string; doubt: string; value: DoubtAnswer }) => rulesApi.answerDoubt(repoId, id, doubt, value),
    onSuccess: done,
    onError: (e) => toast(e.message, { tone: 'err' }),
  })

  if (rules.length === 0) return null
  const needsDecision = (r: RulePreview) => approval(r) === 'borrador' && (r.doubts ?? []).length > 0
  const shown = rules.filter((r) => filter === 'todas' || (filter === 'decision' ? needsDecision(r) : approval(r) === filter))
  const drafts = rules.filter((r) => approval(r) === 'borrador')
  const ready = drafts.filter((r) => (r.doubts ?? []).length === 0)
  const toggle = (set: Set<string>, id: string) => {
    const next = new Set(set)
    if (!next.delete(id)) next.add(id)
    return next
  }
  const chosen = [...selected].filter((id) => rules.some((r) => r.id === id))
  const busy = states.isPending || doubts.isPending || answer.isPending

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
        <p className="text-sm text-slate-400 py-4">{filter === 'decision' ? 'Nada necesita tu decisión: todas las reglas están aprobadas o sin dudas.' : 'No hay reglas en este filtro.'}</p>
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
              onAnswer={(d, value) => answer.mutate({ id: r.id, doubt: d, value })}
              onRevert={() => states.mutate({ ids: [r.id], status: 'borrador' })}
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
          <Button variant="secondary" onClick={() => void rulesApi.viewDocument(repoId).catch((e: Error) => toast(e.message, { tone: 'err' }))} title="Las reglas sin TOML: resumen, ejemplos, dudas y fuente. Se puede imprimir o guardar como PDF">
            <Icon name="doc" className="w-4 h-4" />
            Documento para presentar
          </Button>
          <Button variant="ghost" onClick={() => void rulesApi.downloadDocument(repoId).catch((e: Error) => toast(e.message, { tone: 'err' }))}>
            <Icon name="download" className="w-4 h-4" />
            Markdown
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
