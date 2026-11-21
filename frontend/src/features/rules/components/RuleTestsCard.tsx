import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from '@/shared/hooks/useToast'
import { Button, Card, Chip, ErrorState, Icon, SeverityBadge, Spinner } from '@/shared/ui'
import { ruleTestsQuery, rulesApi, useRuleTests } from '../api/rules.api'
import type { GeneratedTest, RuleTestRow, RuleTestsView, SupportEvidence } from '../types'
import { EVIDENCE, OUTCOME, RULE_TEST_STATE, STATUS, STRENGTH, testsSummary } from '../utils/rules'
import { PermissionMatrixEditor } from './PermissionMatrixEditor'

type Mutate = (fn: () => Promise<RuleTestsView>, done?: string) => void

function useActions(repoId: string): { run: Mutate; pending: boolean } {
  const queryClient = useQueryClient()
  const m = useMutation({
    mutationFn: ({ fn }: { fn: () => Promise<RuleTestsView>; done?: string }) => fn(),
    onSuccess: (view, { done }) => {
      queryClient.setQueryData(ruleTestsQuery(repoId).queryKey, view)
      if (done) toast(done)
    },
    onError: (e) => toast(e.message, { tone: 'err' }),
  })
  return { run: (fn, done) => m.mutate({ fn, done }), pending: m.isPending }
}

/** Dónde parece estar implementada la regla (IA): ayuda a entender el resultado, no cambia el estado. */
function Evidence({ evidence }: { evidence: SupportEvidence }) {
  const e = EVIDENCE[evidence.verdict]
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 p-3">
      <p className="flex flex-wrap items-center gap-2">
        <span className="font-medium">Evidencia de apoyo:</span>
        <Chip tone={e.tone}>{e.label}</Chip>
        <span className="text-xs text-slate-500">{evidence.model ? `${evidence.model} · ` : ''}no cuenta en el resultado</span>
      </p>
      {evidence.summary && <p className="mt-1 text-slate-600 dark:text-slate-300">{evidence.summary}</p>}
      {evidence.places.length > 0 && (
        <ul className="mt-1.5 space-y-0.5 text-xs">
          {evidence.places.map((p) => (
            <li key={`${p.file}:${p.start}`}>
              <code className="font-mono">{p.file}:{p.start === p.end ? p.start : `${p.start}-${p.end}`}</code>
              {p.why && <span className="text-slate-500"> · {p.why}</span>}
            </li>
          ))}
        </ul>
      )}
      {evidence.stale && <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">Es de otra versión de la regla o de otro commit: vuelve a pedirla.</p>}
    </div>
  )
}

/** Prueba de fuerza: ¿la prueba nota que se cambian las líneas de la regla? */
function Strength({ test }: { test: GeneratedTest }) {
  if (test.strength_status === 'corriendo')
    return (
      <p className="flex items-center gap-2 text-slate-500">
        <Spinner className="w-4 h-4" />
        Prueba de fuerza: cambiando las líneas de la regla en el sandbox…
      </p>
    )
  if (!test.strength) return null
  const s = STRENGTH[test.strength.status]
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 p-3">
      <p className="flex flex-wrap items-center gap-2">
        <span className="font-medium">Prueba de fuerza:</span>
        <Chip tone={s.tone}>{s.label}</Chip>
        {test.strength.total > 0 && <span className="text-xs text-slate-500">{test.strength.killed} de {test.strength.total} cambios detectados</span>}
      </p>
      <p className="mt-1 text-xs text-slate-500">{test.strength.detail}</p>
      {test.strength.survivors.length > 0 && (
        <ul className="mt-1.5 space-y-0.5 text-xs">
          {test.strength.survivors.map((v) => (
            <li key={`${v.file}:${v.line}:${v.description}`}>
              <span className="text-slate-500">No lo notó: </span>
              <code className="font-mono">{v.file}:{v.line}</code> <span className="text-slate-600 dark:text-slate-300">{v.description}</span>
            </li>
          ))}
        </ul>
      )}
      {test.strength.status === 'debil' && (
        <p className="mt-1 text-xs text-rose-700 dark:text-rose-300">Pasa, pero seguiría pasando si el código no cumpliera la regla: corrígela antes de aprobarla.</p>
      )}
    </div>
  )
}

function Details({ repoId, row, view, act, busy }: { repoId: string; row: RuleTestRow; view: RuleTestsView; act: Mutate; busy: boolean }) {
  const test = row.test
  const [text, setText] = useState(test?.code ?? '')
  const [showCode, setShowCode] = useState(false)
  const [showMatrix, setShowMatrix] = useState(false)
  const edited = Boolean(test) && text !== test?.code

  return (
    <div className="px-4 pb-4 pt-1 text-sm space-y-2">
      <p className="text-slate-600 dark:text-slate-300">{row.description}</p>
      {row.criterion && <p className="text-xs text-slate-500">Criterio: {row.criterion}</p>}
      {row.repo_tests > 0 && (
        <p className="text-xs text-slate-500">
          El repositorio ya la verifica con {row.repo_tests} prueba(s): esas tienen prioridad en el análisis.
        </p>
      )}
      {!test ? (
        <p className="text-slate-500">Todavía no tiene prueba.</p>
      ) : (
        <>
          <p className="text-xs text-slate-500">
            Tipo <span className="font-mono">{test.tipo}</span>
            {test.endpoints.length > 0 && (
              <>
                {' · '}
                <span className="font-mono">{test.endpoints.join(', ')}</span>
              </>
            )}
            {test.origin === 'manual' ? ' · editada a mano' : test.origin === 'matriz' ? ' · de la matriz de permisos (sin IA)' : test.model ? ` · ${test.model}` : ''}
          </p>
          {test.outdated && <p className="text-amber-700 dark:text-amber-300">La regla cambió desde que se generó la prueba: vuelve a generarla.</p>}
          {test.reason && <p className={test.kind === 'no_implementada' ? 'text-rose-700 dark:text-rose-300' : 'text-slate-600 dark:text-slate-300'}>{test.reason}</p>}
          {test.assumptions.length > 0 && (
            <div>
              <p className="font-medium">Lo que la IA supuso</p>
              <ul className="mt-0.5 list-disc pl-5 text-slate-600 dark:text-slate-300">
                {test.assumptions.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </div>
          )}
          {test.errors.length > 0 && (
            <ul className="list-disc pl-5 text-rose-700 dark:text-rose-300">
              {test.errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
          {test.warnings.length > 0 && (
            <ul className="list-disc pl-5 text-amber-700 dark:text-amber-300">
              {test.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
          {test.run_status === 'corriendo' && (
            <p className="flex items-center gap-2 text-slate-500">
              <Spinner className="w-4 h-4" />
              Corriendo en el sandbox…
            </p>
          )}
          {test.run && (
            <div className="rounded-xl border border-slate-200 dark:border-slate-800 p-3">
              <p className="flex flex-wrap items-center gap-2">
                <span className="font-medium">Primera corrida:</span>
                <Chip tone={STATUS[test.run.verdict].tone}>{STATUS[test.run.verdict].label}</Chip>
                <span className="text-xs text-slate-500">{test.run.detail}</span>
              </p>
              <ul className="mt-2 space-y-1">
                {test.run.tests.map((t) => (
                  <li key={t.name} className="flex flex-wrap items-baseline gap-2 text-xs">
                    <Chip tone={OUTCOME[t.outcome]?.tone ?? 'neutral'}>{OUTCOME[t.outcome]?.label ?? t.outcome}</Chip>
                    <code className="font-mono">{t.name}</code>
                    {t.message && <span className="text-slate-500 break-words">{t.message}</span>}
                  </li>
                ))}
              </ul>
              {test.run.verdict === 'no_cumple' && (
                <p className="mt-2 text-xs text-slate-500">Revisa que la prueba diga lo mismo que la regla antes de aprobarla: si la aprueba el equipo, el código no cumple.</p>
              )}
            </div>
          )}
          <Strength test={test} />
          {test.kind === 'prueba' && (
            <>
              <button type="button" className="text-brand-600 dark:text-brand-300 hover:underline" onClick={() => setShowCode((v) => !v)} aria-expanded={showCode}>
                {showCode ? 'Ocultar el código' : `Ver y editar ${test.file.split('/').pop()}`}
              </button>
              {showCode && (
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  spellCheck={false}
                  aria-label={`Código de la prueba de ${row.id}`}
                  className="w-full min-h-72 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-950 text-slate-100 font-mono text-xs leading-relaxed p-4 outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15"
                />
              )}
            </>
          )}
        </>
      )}
      {row.evidence && <Evidence evidence={row.evidence} />}
      {showMatrix && <PermissionMatrixEditor repoId={repoId} ruleId={row.id} onSave={act} busy={busy} />}
      <div className="flex flex-wrap gap-2 pt-1">
        {edited && (
          <Button onClick={() => act(() => rulesApi.editTest(repoId, row.id, text), 'Prueba guardada: vuelve a correrla')} disabled={busy}>
            <Icon name="save" className="w-4 h-4" />
            Guardar cambios
          </Button>
        )}
        {view.can_generate && (
          <Button variant="secondary" onClick={() => act(() => rulesApi.generateTests(repoId, [row.id]))} disabled={busy}>
            <Icon name="wand" className="w-4 h-4" />
            {test ? 'Volver a generar' : 'Generar prueba'}
          </Button>
        )}
        {test?.kind === 'prueba' && view.sandbox && (
          <Button variant="secondary" onClick={() => act(() => rulesApi.runTests(repoId, [row.id]))} disabled={busy || edited || test.errors.length > 0}>
            <Icon name="play" className="w-4 h-4" />
            Correr
          </Button>
        )}
        {test?.kind === 'prueba' && view.sandbox && (
          <Button
            variant="secondary"
            onClick={() => act(() => rulesApi.strengthTests(repoId, [row.id]))}
            disabled={busy || edited || Boolean(test.strength_blocked)}
            title={test.strength_blocked ?? 'Cambia a propósito las líneas de la regla y comprueba que la prueba lo nota'}
          >
            <Icon name="bolt" className="w-4 h-4" />
            Prueba de fuerza
          </Button>
        )}
        {view.can_explain && (
          <Button variant="secondary" onClick={() => act(() => rulesApi.explainRule(repoId, row.id), 'Evidencia lista')} disabled={busy}>
            <Icon name="search" className="w-4 h-4" />
            {row.evidence ? 'Volver a buscar en el código' : 'Dónde está en el código'}
          </Button>
        )}
        {row.permissions && view.harness_ready && (
          <Button variant="secondary" onClick={() => setShowMatrix((v) => !v)} aria-expanded={showMatrix}>
            <Icon name="users" className="w-4 h-4" />
            {showMatrix ? 'Ocultar la matriz' : 'Matriz de permisos'}
          </Button>
        )}
        {test && !test.approved && (
          <Button onClick={() => act(() => rulesApi.approveTests(repoId, [row.id]))} disabled={busy || edited || Boolean(test.blocked)} title={test.blocked ?? undefined}>
            <Icon name="check" className="w-4 h-4" />
            Aprobar
          </Button>
        )}
        {test && (
          <Button variant="ghost" className="text-rose-600 dark:text-rose-400" onClick={() => act(() => rulesApi.removeTest(repoId, row.id))} disabled={busy}>
            Quitar
          </Button>
        )}
      </div>
    </div>
  )
}

function Row({ repoId, row, view, act, busy }: { repoId: string; row: RuleTestRow; view: RuleTestsView; act: Mutate; busy: boolean }) {
  const [open, setOpen] = useState(false)
  const state = RULE_TEST_STATE[row.state]
  const verdict = row.test?.kind === 'prueba' ? row.test.run?.verdict : row.test?.kind
  return (
    <li className="border-t border-slate-100 dark:border-slate-800">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} className="w-full px-4 py-2.5 flex flex-wrap items-center gap-2 text-left hover:bg-slate-50 dark:hover:bg-slate-900/40">
        <span className="font-mono text-xs text-slate-500">{row.id}</span>
        <span className="font-medium text-sm flex-1 min-w-0">{row.title}</span>
        <SeverityBadge sev={row.severity} />
        {verdict && <Chip tone={STATUS[verdict].tone}>{STATUS[verdict].label}</Chip>}
        {row.test?.strength && row.test.strength.status !== 'no_aplica' && <Chip tone={STRENGTH[row.test.strength.status].tone}>{STRENGTH[row.test.strength.status].label}</Chip>}
        <Chip tone={state.tone}>{state.label}</Chip>
        <Icon name="chevron" className={`w-4 h-4 text-slate-400 transition-transform ${open ? 'rotate-90' : ''}`} />
      </button>
      {/* key: al regenerar o editar, el editor se reinicia con el código del servidor */}
      {open && <Details key={row.test?.updated_at ?? 'sin'} repoId={repoId} row={row} view={view} act={act} busy={busy} />}
    </li>
  )
}

/** Configuración → Reglas de negocio → Pruebas de las reglas (docs/PROPUESTA_REGLAS_VERIFICABLES.md §6.3 y §9). */
export function RuleTestsCard({ repoId, project }: { repoId: string; project: string }) {
  const { data, error, refetch } = useRuleTests(repoId)
  const { run: act, pending } = useActions(repoId)
  const [exporting, setExporting] = useState(false)

  const body = () => {
    if (error) return <ErrorState error={error} onRetry={() => void refetch()} />
    if (!data) return <Spinner className="w-5 h-5" />
    if (!data.cloned) return <p className="text-sm text-slate-500">Analiza el repositorio primero.</p>
    if (!data.rules.length) return <p className="text-sm text-slate-500">{data.error ?? 'Carga las reglas de negocio del proyecto para generar sus pruebas.'}</p>
    const s = testsSummary(data)
    const busy = pending || Boolean(data.busy)
    const exportZip = () => {
      setExporting(true)
      rulesApi
        .exportTests(repoId, `reglas-${project.split('/').pop() || 'proyecto'}.zip`)
        .catch((e: Error) => toast(e.message, { tone: 'err' }))
        .finally(() => setExporting(false))
    }
    return (
      <>
        {!data.harness_ready && (
          <p className="mb-3 text-sm text-slate-500">Aprueba el arnés de pruebas (arriba) para que IA voy escriba una prueba por regla.</p>
        )}
        <div className="flex flex-wrap items-center gap-2 text-sm" aria-label="Resumen de pruebas">
          <Chip tone="success">{s.approved} aprobada(s)</Chip>
          <Chip tone="brand">{s.drafts} en borrador</Chip>
          <Chip>{s.missing} sin prueba</Chip>
          {s.outdated > 0 && <Chip tone="danger">{s.outdated} desactualizada(s)</Chip>}
          {s.weak > 0 && <Chip tone="danger">{s.weak} débil(es)</Chip>}
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {data.can_generate && (
            <Button onClick={() => act(() => rulesApi.generateTests(repoId))} disabled={busy || s.missing + s.outdated === 0}>
              <Icon name="wand" className="w-4 h-4" />
              Generar pruebas ({s.missing + s.outdated})
            </Button>
          )}
          {data.harness_ready && data.sandbox && (
            <Button variant="secondary" onClick={() => act(() => rulesApi.runTests(repoId))} disabled={busy || s.runnable === 0}>
              <Icon name="play" className="w-4 h-4" />
              Correr borradores ({s.runnable})
            </Button>
          )}
          {data.harness_ready && data.sandbox && (
            <Button
              variant="secondary"
              onClick={() => act(() => rulesApi.strengthTests(repoId))}
              disabled={busy || s.measurable === 0}
              title="Cambia a propósito las líneas de cada regla y comprueba que su prueba lo nota (solo las que pasan)"
            >
              <Icon name="bolt" className="w-4 h-4" />
              Prueba de fuerza ({s.measurable})
            </Button>
          )}
          <Button variant="secondary" onClick={() => act(() => rulesApi.approveTests(repoId, s.approvable), 'Pruebas aprobadas: cuentan desde el siguiente análisis')} disabled={busy || s.approvable.length === 0}>
            <Icon name="check" className="w-4 h-4" />
            Aprobar las listas ({s.approvable.length})
          </Button>
          <Button variant="ghost" onClick={exportZip} disabled={exporting || s.approved === 0} title="reglas_negocio.toml, el arnés y las pruebas aprobadas, para hacer commit en tests/reglas/">
            {exporting ? <Spinner className="w-4 h-4" /> : <Icon name="download" className="w-4 h-4" />}
            Exportar para el repo
          </Button>
        </div>
        {data.busy && (
          <p role="status" className="mt-3 flex items-center gap-2 text-sm text-slate-500">
            <Spinner className="w-4 h-4" />
            {data.busy.kind === 'generando'
              ? `La IA está escribiendo la prueba ${Math.min(data.busy.done + 1, data.busy.total)} de ${data.busy.total}${data.busy.current ? ` (${data.busy.current})` : ''}…`
              : data.busy.kind === 'fuerza'
                ? `Prueba de fuerza de ${data.busy.total} prueba(s): cambia las líneas de cada regla y vuelve a correrla, puede tardar unos minutos.`
                : `Corriendo ${data.busy.total} prueba(s) en el sandbox: instala las dependencias, puede tardar unos minutos.`}
          </p>
        )}
        {data.messages.length > 0 && (
          <ul className="mt-3 list-disc pl-5 text-sm text-amber-700 dark:text-amber-300">
            {data.messages.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        )}
        <ul className="mt-4 -mx-5 sm:-mx-6 border-b border-slate-100 dark:border-slate-800">
          {data.rules.map((row) => (
            <Row key={row.id} repoId={repoId} row={row} view={data} act={act} busy={busy} />
          ))}
        </ul>
        <p className="mt-3 text-xs text-slate-400">
          Solo cuentan en el análisis las pruebas aprobadas. Una prueba rota (falla al preparar el escenario o intenta salir a la red) no culpa al código: corrígela o vuelve a generarla.
          La evidencia y la prueba de fuerza ayudan a revisarlas antes de aprobar; no cambian el resultado.
        </p>
      </>
    )
  }

  return (
    <Card className="p-5 sm:p-6">
      <h2 className="font-semibold mb-3">Pruebas de las reglas</h2>
      {body()}
    </Card>
  )
}
