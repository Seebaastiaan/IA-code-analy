import { Link } from 'react-router'
import { CAT } from '@/shared/constants/categories'
import { paths } from '@/shared/constants/paths'
import { CATEGORIES } from '@/shared/types/common'
import { Card, Icon, ProgressBar, ScoreRing, Spinner, StatusChip, buttonClass } from '@/shared/ui'
import { timeAgo } from '@/shared/utils/format'
import { useReanalyze } from '../hooks/useReanalyze'
import type { Repo } from '../types'

export function RepoCard({ repo }: { repo: Repo }) {
  const reanalyze = useReanalyze()

  return (
    <Card className="p-5 flex flex-col">
      <div className="flex items-start gap-3">
        <span className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-800 grid place-items-center text-slate-500">
          <Icon name="folder" />
        </span>
        <div className="flex-1 min-w-0">
          <p className="font-semibold truncate">{repo.name}</p>
          <p className="text-xs text-slate-400 flex items-center gap-1 mt-0.5">
            <Icon name="branch" className="w-3 h-3" />
            {repo.branch} · {repo.files} archivos .py
          </p>
        </div>
        <StatusChip status={repo.status} />
      </div>

      {repo.status === 'analizando' ? (
        <div className="mt-5 flex-1 rounded-xl bg-brand-50 dark:bg-brand-500/10 p-3 text-xs text-brand-700 dark:text-brand-300 flex items-center gap-2">
          <Spinner className="w-3.5 h-3.5" />
          {repo.progress ? `Ejecutando ${repo.progress.name} (paso ${repo.progress.step + 1} de ${repo.progress.total})…` : 'En cola…'}
        </div>
      ) : repo.status === 'error' ? (
        <div className="mt-5 flex-1 rounded-xl bg-rose-50 dark:bg-rose-500/10 p-3 text-xs text-rose-700 dark:text-rose-300 font-mono">{repo.error}</div>
      ) : repo.scores ? (
        <div className="flex items-center gap-4 mt-5">
          <ScoreRing value={repo.scores.global} size={64} stroke={6} />
          <div className="flex-1 space-y-2">
            {CATEGORIES.map((k) => (
              <div key={k} className="flex items-center gap-2 text-xs">
                <span className="w-16 text-slate-500 truncate">{CAT[k].shortLabel}</span>
                <div className="flex-1">
                  <ProgressBar value={repo.scores![k]} className={CAT[k].bar} />
                </div>
                <span className="w-6 text-right font-mono tabular-nums">{repo.scores![k]}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
        <span className="text-xs text-slate-400 flex items-center gap-1">
          <Icon name="clock" className="w-3.5 h-3.5" />
          {repo.status === 'analizando' ? 'en curso' : repo.last_analyzed_at ? timeAgo(repo.last_analyzed_at) : '—'}
        </span>
        <div className="flex gap-1">
          {repo.status === 'analizando' && repo.progress && (
            <Link to={paths.job(repo.progress.job_id)} className={buttonClass('ghost')}>
              Ver progreso
            </Link>
          )}
          {repo.status !== 'analizando' && (
            <button type="button" onClick={() => reanalyze.mutate(repo)} disabled={reanalyze.isPending} className={buttonClass('ghost')} title="Re-analizar" aria-label={`Re-analizar ${repo.name}`}>
              <Icon name="refresh" className="w-4 h-4" />
            </button>
          )}
          {repo.files > 0 && (
            <Link to={paths.files(repo.id)} className={buttonClass('ghost')} title="Ver archivos" aria-label={`Ver archivos de ${repo.name}`}>
              <Icon name="folder" className="w-4 h-4" />
              <span className="hidden sm:inline">Archivos</span>
            </Link>
          )}
          {repo.last_report_id && (
            <Link to={paths.report(repo.id, repo.last_report_id)} className={buttonClass('ghost', 'text-brand-600 dark:text-brand-300')}>
              Reporte <Icon name="chevron" className="w-4 h-4" />
            </Link>
          )}
        </div>
      </div>
    </Card>
  )
}
