import { useState } from 'react'
import { Link } from 'react-router'
import { paths } from '@/shared/constants/paths'
import { Button, Card, Chip, EmptyState, ErrorState, Icon, PageLoader, SegmentedControl, SeverityBadge, Spinner } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import { useReportRules } from '../api/rules.api'
import { useFixRule } from '../hooks/useFixRule'
import type { BusinessRuleResult, BusinessRules } from '../types'
import { draftCount, filterRules, LEVEL, LIGHT, OUTCOME, plain, plainSummary, STATUS, testFunction, type StatusFilter } from '../utils/rules'

const FILTERS: { value: StatusFilter; label: string }[] = [
  { value: 'todas', label: 'Todas' },
  { value: 'no_cumple', label: 'No cumple' },
  { value: 'prueba_rota', label: 'Prueba rota' },
  { value: 'sin_verificar', label: 'Sin verificar' },
  { value: 'cumple', label: 'Cumple' },
]

function Notices({ data, repoId }: { data: BusinessRules; repoId: string }) {
  const withTests = data.rules.some((r) => r.tests.length)
  return (
    <>
      {data.origin === 'app' && data.repo_error && (
        <div className="px-5 py-2.5 text-sm bg-amber-50 text-amber-800 dark:bg-amber-500/10 dark:text-amber-200 border-b border-amber-200/60 dark:border-amber-500/20">
          <p>
            Reglas corregidas en la app: el archivo del repositorio tiene errores y no se usó.{' '}
            <Link to={paths.settings(repoId, 'reglas')} className="font-medium underline">
              Descarga las corregidas para subirlas al repo
            </Link>
            .
          </p>
          <p className="mt-1 font-mono text-xs">{data.repo_error}</p>
        </div>
      )}
      {withTests && !data.tests_ran && (
        <p className="px-5 py-2.5 text-sm text-slate-500 bg-slate-50/60 dark:bg-slate-950/40 border-b border-slate-100 dark:border-slate-800">
          Las pruebas ligadas a reglas no se ejecutaron en este análisis (sin sandbox o sin pytest): sus reglas quedan sin verificar.
        </p>
      )}
      {data.warnings.length > 0 && (
        <div className="px-5 py-2.5 text-sm border-b border-slate-100 dark:border-slate-800">
          <p className="font-medium text-amber-700 dark:text-amber-300">Avisos</p>
          <ul className="mt-1 list-disc pl-5 text-slate-500 space-y-0.5">
            {data.warnings.map((w) => (
              <li key={w} className="font-mono text-xs">
                {w}
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  )
}

function RuleDetail({ rule, repoId }: { rule: BusinessRuleResult; repoId: string }) {
  const fix = useFixRule(repoId)
  const violated = rule.status === 'no_cumple' || rule.status === 'no_implementada'
  return (
    <div className="px-4 sm:px-5 pb-4 pt-1 space-y-3 text-sm break-words bg-slate-50/60 dark:bg-slate-950/30">
      {violated && (
        <div className="rounded-xl border border-rose-200 dark:border-rose-500/30 bg-rose-50/60 dark:bg-rose-500/10 p-3.5">
          <p className="font-medium text-rose-700 dark:text-rose-300">El documento manda: el código tiene que seguir a la regla.</p>
          <p className="mt-0.5 text-xs text-slate-600 dark:text-slate-300">
            La IA propone el cambio mínimo en el código (nunca en la regla ni en su prueba) y lo ves como diff en el editor antes de guardar.
          </p>
          <Button className="mt-2" onClick={() => fix.mutate(rule.id)} disabled={fix.isPending}>
            {fix.isPending ? <Spinner className="w-4 h-4" /> : <Icon name="sparkle" className="w-4 h-4" />}
            Corregir con IA
          </Button>
        </div>
      )}
      <p className="text-slate-600 dark:text-slate-300 break-words">{rule.description}</p>
      {rule.criterion && (
        <p>
          <span className="text-slate-400">Criterio de aceptación: </span>
          {rule.criterion}
        </p>
      )}
      {(rule.story || rule.owner || rule.paths.length > 0) && (
        <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
          {rule.story && <span>Historia: {rule.story}</span>}
          {rule.owner && <span>Responsable: {rule.owner}</span>}
          {rule.paths.length > 0 && <span className="font-mono">Rutas: {rule.paths.join(', ')}</span>}
        </p>
      )}
      <p className="text-slate-500">{rule.detail}</p>

      {rule.tests.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1.5">Pruebas</p>
          <ul className="space-y-1">
            {rule.tests.map((t) => (
              <li key={t.name} className="flex flex-wrap items-center gap-2">
                <Chip tone={OUTCOME[t.outcome]?.tone ?? 'neutral'}>{OUTCOME[t.outcome]?.label ?? t.outcome}</Chip>
                <Link to={paths.editor(repoId, { file: t.file, line: t.line })} className="font-mono text-xs hover:underline" title={t.name}>
                  {t.file}:{t.line} · {testFunction(t.name)}
                </Link>
                {t.message && <span className="text-xs text-rose-600 dark:text-rose-400 truncate max-w-full">{t.message}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {rule.evidence.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1.5">
            Evidencia del patrón{rule.evidence_total > rule.evidence.length && ` (${rule.evidence.length} de ${rule.evidence_total})`}
          </p>
          <ul className="space-y-1">
            {rule.evidence.map((e) => (
              <li key={`${e.file}:${e.line}:${e.text}`} className="font-mono text-xs flex gap-2 min-w-0">
                <Link to={paths.editor(repoId, { file: e.file, line: e.line })} className="shrink-0 text-brand-600 dark:text-brand-300 hover:underline">
                  {e.file}:{e.line}
                </Link>
                <span className="truncate text-slate-500">{e.text}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {rule.level === 'ninguno' && rule.status === 'sin_verificar' && (
        <p className="text-xs text-slate-500">
          Para comprobarla, pulsa «Preparar todo» en{' '}
          <Link to={paths.settings(repoId, 'reglas')} className="text-brand-600 dark:text-brand-300 hover:underline">
            Configuración → Reglas
          </Link>
          : el programa le escribe una prueba.
        </p>
      )}
    </div>
  )
}

/** Vista Reglas del reporte: matriz regla → estado → evidencia (prueba o archivo:línea). */
export function RulesTab({ repoId, reportId }: { repoId: string; reportId: string }) {
  const { data, error, isPending, refetch } = useReportRules(repoId, reportId)
  const [status, setStatus] = useState<StatusFilter>('todas')
  const [open, setOpen] = useState<string | null>(null)

  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />
  if (isPending) return <PageLoader />

  const settings = (
    <Link to={paths.settings(repoId, 'reglas')} className="text-brand-600 dark:text-brand-300 hover:underline">
      Configuración → Reglas de negocio
    </Link>
  )
  if (!data.checked)
    return (
      <Card className="mt-4">
        <EmptyState icon="clock" title="Este análisis es anterior a las reglas de negocio">
          Vuelve a analizar el repositorio para verificarlas.
        </EmptyState>
      </Card>
    )
  if (!data.source)
    return (
      <Card className="mt-4">
        <EmptyState icon="doc" title="Este proyecto todavía no tiene reglas de negocio">
          En {settings} sube el documento de requisitos (o usa el del repositorio): el programa saca las reglas y solo te pregunta lo que no puede decidir.
        </EmptyState>
      </Card>
    )
  const drafts = draftCount(data.warnings)
  if (!data.error && data.summary.total === 0 && drafts > 0)
    return (
      <Card className="mt-4">
        <EmptyState icon="clock" title={`Tus ${drafts} reglas todavía no se comprueban`}>
          <p>Están en borrador. Contesta sus preguntas y pulsa «Preparar todo»; después vuelve a analizar para ver aquí cuáles se cumplen.</p>
          <Link to={paths.settings(repoId, 'reglas')} className="mt-3 inline-flex items-center gap-1.5 font-medium text-brand-600 dark:text-brand-300 hover:underline">
            Ir a Reglas
            <Icon name="arrow" className="w-4 h-4" />
          </Link>
        </EmptyState>
      </Card>
    )
  if (data.error)
    return (
      <Card className="mt-4 p-5">
        <h2 className="font-semibold flex items-center gap-2 text-rose-600 dark:text-rose-400">
          <Icon name="alert" className="w-4 h-4" />
          {data.source} no es válido
        </h2>
        <p className="mt-2 font-mono text-sm">{data.error}</p>
        <p className="mt-3 text-sm text-slate-500">Las reglas no se verificaron en este análisis. Valida el archivo en {settings}.</p>
      </Card>
    )

  const list = filterRules(data.rules, status)
  const { summary } = data

  return (
    <Card className="mt-4 overflow-hidden">
      <div className="p-4 sm:px-5 border-b border-slate-200 dark:border-slate-800 flex flex-col lg:flex-row gap-3 lg:items-center lg:justify-between">
        <div className="min-w-0">
          <h2 className="font-semibold">Reglas de negocio · {data.project}</h2>
          <p className="text-xs text-slate-400 mt-0.5 font-mono truncate">{data.source}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2" aria-label="Resumen de reglas">
          <Chip tone="success">{summary.cumple} cumplen</Chip>
          <Chip tone="danger">{summary.no_cumple} no cumplen</Chip>
          {summary.no_implementada > 0 && <Chip tone="danger">{summary.no_implementada} no implementada(s)</Chip>}
          {summary.prueba_rota > 0 && <Chip tone="brand">{summary.prueba_rota} con la prueba rota</Chip>}
          <Chip>{summary.sin_verificar} sin verificar</Chip>
          {summary.fuera_del_codigo > 0 && <Chip>{summary.fuera_del_codigo} fuera del código</Chip>}
        </div>
      </div>
      {summary.total > 0 && (
        <p className="px-4 sm:px-5 py-3 text-sm font-medium border-b border-slate-100 dark:border-slate-800">{plainSummary(data.rules)}</p>
      )}
      {!!data.regressions?.length && (
        <p role="alert" className="px-4 sm:px-5 py-3 text-sm border-b border-rose-100 dark:border-rose-900/50 bg-rose-50 dark:bg-rose-950/30 text-rose-800 dark:text-rose-200">
          {data.regressions.length === 1 ? 'Dejó de cumplirse' : `Dejaron de cumplirse ${data.regressions.length} reglas`} desde el análisis #{data.previous_num}:{' '}
          {data.regressions
            .map((id) => {
              const r = data.rules.find((x) => x.id === id)
              return r ? `${id} · ${r.title}` : id
            })
            .join('; ')}
          . Míralas primero: algo que cambió en el código las rompió.
        </p>
      )}
      <Notices data={data} repoId={repoId} />
      <div className="px-4 sm:px-5 py-3 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between gap-3">
        <SegmentedControl options={FILTERS} value={status} onChange={setStatus} />
        <Link to={paths.settings(repoId)} className="hidden sm:block text-xs text-slate-400 hover:underline" title="Las reglas pesan 0 % en el score hasta que subas su peso en Configuración → General">
          Pesan 0 % en el score por defecto: ajustar
        </Link>
      </div>

      {!summary.total ? (
        <EmptyState icon="doc" title={`${data.source} no declara reglas`} />
      ) : !list.length ? (
        <EmptyState title="Sin reglas con ese estado" />
      ) : (
        <table className="block md:table w-full text-sm">
          <thead className="hidden md:table-header-group text-left text-xs text-slate-400 uppercase tracking-wide">
            <tr className="border-b border-slate-100 dark:border-slate-800">
              <th className="px-5 py-2 font-medium">Regla</th>
              <th className="px-3 py-2 font-medium">Severidad</th>
              <th className="px-3 py-2 font-medium">Estado</th>
              <th className="px-3 py-2 font-medium">Verificación</th>
              <th className="px-5 py-2 font-medium">Evidencia</th>
            </tr>
          </thead>
          {list.map((r) => {
            const expanded = open === r.id
            const evidence = r.tests.length ? `${r.tests.length} prueba(s)` : r.evidence_total ? `${r.evidence_total} coincidencia(s)` : '—'
            return (
              <tbody key={r.id} className="block md:table-row-group border-b border-slate-100 dark:border-slate-800 last:border-0">
                <tr
                  className="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/40 flex flex-wrap items-center gap-2 px-4 py-3 md:table-row md:p-0"
                  onClick={() => setOpen(expanded ? null : r.id)}
                >
                  <td className="w-full md:w-auto md:px-5 md:py-3">
                    {/* El clic sube a la fila; el botón da el foco y el estado para teclado y lectores de pantalla */}
                    <button type="button" aria-expanded={expanded} className="text-left flex items-start gap-2 min-w-0">
                      <Icon name="chevron" className={cn('w-4 h-4 mt-0.5 shrink-0 text-slate-400 transition', expanded && 'rotate-90')} />
                      <span className="min-w-0">
                        <span className="font-mono text-xs text-slate-500 mr-2">{r.id}</span>
                        <span className="font-medium break-words">{r.title}</span>
                        <span className="block text-xs font-normal text-slate-500 mt-0.5">
                          {LIGHT[plain(r).light].dot} {plain(r).text}
                        </span>
                      </span>
                    </button>
                  </td>
                  <td className="md:px-3 md:py-3">
                    <SeverityBadge sev={r.severity} />
                  </td>
                  <td className="md:px-3 md:py-3">
                    <Chip tone={STATUS[r.status].tone}>{STATUS[r.status].label}</Chip>
                  </td>
                  <td className="md:px-3 md:py-3 text-xs text-slate-500">{LEVEL[r.level]}</td>
                  <td className="md:px-5 md:py-3 text-xs text-slate-500">{evidence}</td>
                </tr>
                {expanded && (
                  <tr className="block md:table-row">
                    <td colSpan={5} className="block md:table-cell">
                      <RuleDetail rule={r} repoId={repoId} />
                    </td>
                  </tr>
                )}
              </tbody>
            )
          })}
        </table>
      )}
    </Card>
  )
}
