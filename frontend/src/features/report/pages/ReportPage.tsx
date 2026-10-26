import { useEffect } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { FindingDrawer, useFindingParam } from '@/features/findings'
import { useSelectedRepo } from '@/features/repos'
import { ShareModal } from '@/features/share'
import { paths } from '@/shared/constants/paths'
import { ErrorState, Icon, PageLoader, Tabs } from '@/shared/ui'
import { useReport } from '../api/report.api'
import { ComplexityTab, CoverageTab, FindingsTab } from '../components/ReportTabs'
import { ReportHeader } from '../components/ReportHeader'
import { useReportFilters, type ReportTab } from '../hooks/useReportFilters'

const TABS: { value: ReportTab; label: string }[] = [
  { value: 'hallazgos', label: 'Hallazgos' },
  { value: 'cobertura', label: 'Cobertura' },
  { value: 'complejidad', label: 'Complejidad' },
]

export default function ReportPage() {
  const { repoId = '', reportId = 'latest' } = useParams()
  const { data: report, isPending, error, refetch } = useReport(repoId, reportId)
  const filters = useReportFilters()
  const { findingId, open, close } = useFindingParam()
  const [params, setParams] = useSearchParams()
  const select = useSelectedRepo((s) => s.select)

  // El repo del reporte pasa a ser el activo (sidebar, búsqueda global)
  useEffect(() => {
    if (repoId) select(repoId)
  }, [repoId, select])

  const setShare = (on: boolean) =>
    setParams((p) => {
      if (on) p.set('share', '1')
      else p.delete('share')
      return p
    })

  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />
  if (isPending) return <PageLoader />

  const finding = report.findings.find((f) => f.id === findingId)

  return (
    <>
      <nav aria-label="Ruta" className="flex items-center gap-1.5 text-sm text-slate-500 mb-4">
        <Link to={paths.repos()} className="hover:text-slate-800 dark:hover:text-slate-200">
          Repositorios
        </Link>
        <Icon name="chevron" className="w-3.5 h-3.5" />
        <span className="truncate">{report.repo_name}</span>
        <Icon name="chevron" className="w-3.5 h-3.5" />
        <span className="text-slate-800 dark:text-slate-200 font-medium">#{report.num}</span>
      </nav>

      <ReportHeader report={report} cat={filters.cat} onCat={(cat) => filters.set({ cat })} onShare={() => setShare(true)} />

      <Tabs className="mt-6" options={TABS} value={filters.tab} onChange={(tab) => filters.set({ tab })} />

      {filters.tab === 'hallazgos' ? (
        <FindingsTab findings={report.findings} q={filters.q} sev={filters.sev} cat={filters.cat} onChange={filters.set} onClear={filters.clear} onOpen={open} />
      ) : filters.tab === 'cobertura' ? (
        <CoverageTab coverage={report.coverage} threshold={report.thresholds.cov} />
      ) : (
        <ComplexityTab complexity={report.complexity} />
      )}

      {finding && <FindingDrawer finding={finding} repoId={repoId} onClose={close} />}
      {params.get('share') === '1' && <ShareModal reportId={report.id} title={`${report.repo_name} · análisis #${report.num}`} onClose={() => setShare(false)} />}
    </>
  )
}
