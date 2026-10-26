import { Link } from 'react-router'
import type { Repo } from '@/features/repos'
import { paths } from '@/shared/constants/paths'
import { toast } from '@/shared/hooks/useToast'
import { Card, Icon, ScoreRing, Spinner, StatusChip, buttonClass } from '@/shared/ui'
import { timeAgo } from '@/shared/utils/format'
import { navigateTo } from '@/shared/utils/navigation'

function Action({ repo }: { repo: Repo }) {
  if (repo.status === 'listo' && repo.last_report_id)
    return (
      <Link to={paths.report(repo.id, repo.last_report_id)} className={buttonClass('ghost')}>
        Ver reporte
      </Link>
    )
  if (repo.status === 'error')
    return (
      <button
        type="button"
        className={buttonClass('ghost')}
        onClick={() =>
          toast(repo.error ?? 'El último análisis falló', {
            tone: 'err',
            action: { label: 'Reintentar', onClick: () => navigateTo(paths.analyze({ url: repo.url, branch: repo.branch })) },
          })
        }
      >
        Ver error
      </button>
    )
  return (
    <Link to={repo.progress ? paths.job(repo.progress.job_id) : paths.repos()} className={buttonClass('ghost')}>
      Ver progreso
    </Link>
  )
}

export function RecentAnalyses({ repos }: { repos: Repo[] }) {
  return (
    <Card className="mt-4 overflow-hidden">
      <div className="p-5 flex items-center justify-between border-b border-slate-200 dark:border-slate-800">
        <h2 className="font-semibold">Análisis recientes</h2>
        <Link to={paths.repos()} className={buttonClass('ghost')}>
          Ver repositorios <Icon name="chevron" className="w-4 h-4" />
        </Link>
      </div>
      <div className="divide-y divide-slate-100 dark:divide-slate-800">
        {repos.map((r) => (
          <div key={r.id} className="flex flex-wrap sm:flex-nowrap items-center gap-x-4 gap-y-2 px-5 py-3.5">
            {r.scores && r.status === 'listo' ? (
              <ScoreRing value={r.scores.global} size={40} stroke={4} />
            ) : (
              <span className="w-10 h-10 rounded-full grid place-items-center bg-slate-100 dark:bg-slate-800 text-slate-400">
                {r.status === 'error' ? <Icon name="alert" className="w-4 h-4" /> : <Spinner />}
              </span>
            )}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{r.name}</p>
              <p className="text-xs text-slate-400 flex items-center gap-1">
                <Icon name="branch" className="w-3 h-3" />
                {r.branch} · {r.status === 'analizando' ? 'en curso' : r.last_analyzed_at ? timeAgo(r.last_analyzed_at) : '—'}
              </p>
            </div>
            <StatusChip status={r.status} />
            <Action repo={r} />
          </div>
        ))}
      </div>
    </Card>
  )
}
