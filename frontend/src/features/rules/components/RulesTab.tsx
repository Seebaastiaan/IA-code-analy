import { useState } from 'react'
import { Link } from 'react-router'
import { paths } from '@/shared/constants/paths'
import { Card, Chip, EmptyState, ErrorState, Icon, PageLoader, SegmentedControl, SeverityBadge } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import { useReportRules } from '../api/rules.api'
import type { BusinessRuleResult, BusinessRules } from '../types'
import { filterRules, LEVEL, OUTCOME, STATUS, testFunction, testName, type StatusFilter } from '../utils/rules'

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
      {data.origin === 'app' && !data.repo_error && (
        <p className="px-5 py-2.5 text-sm bg-amber-50 text-amber-800 dark:bg-amber-500/10 dark:text-amber-200 border-b border-amber-200/60 dark:border-amber-500/20">
          Reglas cargadas en la app: no están en el repositorio y no cuentan como entregable.{' '}
          <Link to={paths.settings(repoId, 'reglas')} className="font-medium underline">
            Descárgalas para subirlas al repo
          </Link>
          .
        </p>
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
  return (
    <div className="px-5 pb-4 pt-1 space-y-3 text-sm bg-slate-50/60 dark:bg-slate-950/30">
      <p className="text-slate-600 dark:text-slate-300">{rule.description}</p>
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

      {rule.level === 'ninguno' && (
        <p className="text-xs text-slate-500">
          Para verificarla, márcale una prueba con <code className="font-mono">@pytest.mark.regla("{rule.id}")</code> (o llámala{' '}
          <code className="font-mono">{testName(rule.id)}</code>) o agrega un patrón <code className="font-mono">prohibido</code> /{' '}
          <code className="font-mono">obligatorio</code>.
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
        <EmptyState icon="doc" title="El proyecto no declara reglas de negocio">
          Agrega <code className="font-mono">reglas_negocio.toml</code> a la raíz del repositorio. La plantilla está en {settings}.
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
      <Notices data={data} repoId={repoId} />
      <div className="px-4 sm:px-5 py-3 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between gap-3">
        <SegmentedControl options={FILTERS} value={status} onChange={setStatus} />
        <span className="hidden sm:block text-xs text-slate-400">Aún no cuentan en el score</span>
      </div>

      {!summary.total ? (
        <EmptyState icon="doc" title={`${data.source} no declara reglas`} />
      ) : !list.length ? (
        <EmptyState title="Sin reglas con ese estado" />
      ) : (
        <table className="w-full text-sm">
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
              <tbody key={r.id} className="border-b border-slate-100 dark:border-slate-800 last:border-0">
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
                        <span className="font-medium">{r.title}</span>
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
