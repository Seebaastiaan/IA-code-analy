import { useEffect } from 'react'
import { Link } from 'react-router'
import { useSelectedRepo } from '@/features/repos'
import { SEV } from '@/shared/constants/severities'
import { paths } from '@/shared/constants/paths'
import { CATEGORIES } from '@/shared/types/common'
import { Card, EmptyState, ErrorState, Icon, PageHeader, Select, Skeleton, buttonClass } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import { useDashboard } from '../api/dashboard.api'
import { RecentAnalyses } from '../components/RecentAnalyses'
import { CategoryKpiCard, GlobalScoreCard } from '../components/ScoreCards'
import { TrendChart } from '../components/TrendChart'

const today = () => {
  const s = new Intl.DateTimeFormat('es', { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date())
  return s.charAt(0).toUpperCase() + s.slice(1)
}

export default function DashboardPage() {
  const { repoId, select } = useSelectedRepo()
  const { data, isPending, error, refetch } = useDashboard(repoId)
  const sel = data?.selected

  // El servidor elige un repo si no hay ninguno seleccionado: lo recordamos
  useEffect(() => {
    if (sel && sel.repo.id !== repoId) select(sel.repo.id)
  }, [sel, repoId, select])

  const newAnalysis = (
    <Link to={paths.analyze()} className={buttonClass('primary')}>
      <Icon name="plus" className="w-4 h-4" />
      Nuevo análisis
    </Link>
  )

  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />
  if (isPending)
    return (
      <div className="space-y-4">
        <Skeleton className="h-16 w-72" />
        <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-36" />
          ))}
        </div>
        <Skeleton className="h-72" />
      </div>
    )

  const ready = data.repos.filter((r) => r.last_report_id)

  return (
    <>
      <PageHeader
        eyebrow={`${today()} · ${data.active_repos} repositorios activos`}
        title="Resumen del equipo"
        actions={
          <>
            {ready.length > 0 && (
              <Select value={sel?.repo.id ?? ''} onChange={(e) => select(e.target.value)} aria-label="Repositorio" className="sm:w-56">
                {ready.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </Select>
            )}
            {newAnalysis}
          </>
        }
      />

      {!sel ? (
        <Card>
          <EmptyState icon="doc" title="Aún no hay análisis">
            <p>Analiza un repositorio para ver su score y tendencias.</p>
            <div className="mt-3">{newAnalysis}</div>
          </EmptyState>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <GlobalScoreCard name={sel.repo.name} scores={sel.scores} prev={sel.prev_scores} threshold={data.thresholds.score} />
            {CATEGORIES.map((k) => (
              <CategoryKpiCard key={k} cat={k} value={sel.scores[k]} prev={sel.prev_scores?.[k] ?? null} />
            ))}
          </div>

          <div className="grid lg:grid-cols-3 gap-4 mt-4">
            <Card className="p-5 lg:col-span-2">
              <div className="flex items-start justify-between gap-3 mb-3">
                <div>
                  <h2 className="font-semibold">Tendencia</h2>
                  <p className="text-sm text-slate-500 dark:text-slate-400">Últimos {sel.history.length} análisis · toca la leyenda para ocultar series</p>
                </div>
              </div>
              <TrendChart history={sel.history} />
            </Card>

            <Card className="p-5 flex flex-col">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-semibold">Atención prioritaria</h2>
                <span className="text-xs text-slate-400">{sel.open_findings} abiertos</span>
              </div>
              <div className="space-y-2 flex-1">
                {sel.top_findings.length ? (
                  sel.top_findings.map((f) => (
                    <div key={f.id} className="w-full text-left flex gap-3 p-3 rounded-xl border border-slate-100 dark:border-slate-800">
                      <span className={cn('mt-1.5 w-2 h-2 shrink-0 rounded-full', SEV[f.sev].dot)} />
                      <div className="min-w-0">
                        <p className="text-sm font-medium leading-snug">{f.msg}</p>
                        <p className="text-xs font-mono text-slate-400 mt-0.5 truncate">
                          {f.file}:{f.line} · {f.rule}
                        </p>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">Sin hallazgos abiertos</p>
                )}
              </div>
              <Link to={paths.files(sel.repo.id)} className={buttonClass('secondary', 'mt-3 w-full')}>
                Ver archivos del repo <Icon name="arrow" className="w-4 h-4" />
              </Link>
              <p className="mt-2 text-xs text-slate-400 text-center">El reporte completo de hallazgos llega en el Sprint 7</p>
            </Card>
          </div>
        </>
      )}

      <RecentAnalyses repos={data.repos} />
    </>
  )
}
