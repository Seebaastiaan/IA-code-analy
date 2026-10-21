import { Link, useMatch } from 'react-router'
import { paths } from '@/shared/constants/paths'
import { Icon, Spinner } from '@/shared/ui'
import { useJobStore } from '../store/job.store'

/** Indicador global del análisis en curso (header). */
export function JobPill() {
  const job = useJobStore((s) => s.job)
  const onJobPage = useMatch('/analyze/jobs/:jobId')
  if (!job || job.status === 'done' || job.status === 'cancelled' || onJobPage) return null

  const pct = Math.round((job.step / job.total) * 100)
  const base = 'hidden sm:inline-flex items-center gap-2 rounded-xl text-xs font-semibold px-3 py-2'

  return job.status === 'running' ? (
    <Link to={paths.job(job.id)} className={`${base} bg-brand-50 dark:bg-brand-500/10 text-brand-700 dark:text-brand-300`}>
      <Spinner className="w-3.5 h-3.5" />
      Analizando {pct}%
    </Link>
  ) : (
    <Link to={paths.job(job.id)} className={`${base} bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-300`}>
      <Icon name="alert" className="w-3.5 h-3.5" />
      Falló
    </Link>
  )
}
