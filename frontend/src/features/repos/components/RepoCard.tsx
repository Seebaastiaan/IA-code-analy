import { Link } from 'react-router'
import { paths } from '@/shared/constants/paths'
import { Card, Icon, Spinner, StatusChip, buttonClass } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import { timeAgo } from '@/shared/utils/format'
import { useReanalyze } from '../hooks/useReanalyze'
import type { Repo } from '../types'

/** Etapas del análisis en el Sprint 5 y lo que llega después. */
function Stage({ done, label, next }: { done: boolean; label: string; next?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium',
        done ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300' : 'bg-slate-100 text-slate-400 dark:bg-slate-800',
      )}
    >
      {done ? <Icon name="check" className="w-3 h-3" /> : <Icon name="clock" className="w-3 h-3" />}
      {label}
      {next && <span className="font-mono">{next}</span>}
    </span>
  )
}

export function RepoCard({ repo, selected, onSelect }: { repo: Repo; selected: boolean; onSelect: () => void }) {
  const reanalyze = useReanalyze()

  return (
    <Card className={cn('p-5 flex flex-col transition', selected && 'ring-2 ring-brand-500/60')}>
      <button type="button" onClick={onSelect} className="flex items-start gap-3 text-left" aria-label={`Ver historial de ${repo.name}`}>
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
      </button>

      {repo.status === 'analizando' ? (
        <div className="mt-5 flex-1 rounded-xl bg-brand-50 dark:bg-brand-500/10 p-3 text-xs text-brand-700 dark:text-brand-300 flex items-center gap-2">
          <Spinner className="w-3.5 h-3.5" />
          {repo.progress ? `Ejecutando ${repo.progress.name} (paso ${repo.progress.step + 1} de ${repo.progress.total})…` : 'En cola…'}
        </div>
      ) : repo.status === 'error' ? (
        <div className="mt-5 flex-1 rounded-xl bg-rose-50 dark:bg-rose-500/10 p-3 text-xs text-rose-700 dark:text-rose-300 font-mono">{repo.error}</div>
      ) : repo.last_report_num ? (
        <div className="mt-5 flex-1 space-y-3">
          <div className="rounded-xl bg-slate-50 dark:bg-slate-950 p-3 text-xs flex items-center gap-3">
            <Icon name="save" className="w-4 h-4 text-slate-400" />
            <span>
              Análisis <b>#{repo.last_report_num}</b> guardado
              {repo.commit && <span className="font-mono text-slate-500"> · {repo.commit}</span>}
            </span>
            <span className="ml-auto text-slate-400">{repo.reports} en total</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <Stage done label="Clonado" />
            <Stage done label="Entorno aislado" />
            <Stage done label={repo.findings ? `Seguridad · ${repo.findings.alta + repo.findings.media + repo.findings.baja} hallazgo(s)` : 'Seguridad'} />
            <Stage done={false} label="Score" next="S6" />
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
          <Link to={paths.settings(repo.id)} className={buttonClass('ghost')} title="Configuración" aria-label={`Configuración de ${repo.name}`}>
            <Icon name="sliders" className="w-4 h-4" />
          </Link>
          {repo.files > 0 && (
            <Link to={paths.files(repo.id)} className={buttonClass('ghost', 'text-brand-600 dark:text-brand-300')} title="Ver archivos" aria-label={`Ver archivos de ${repo.name}`}>
              Archivos <Icon name="chevron" className="w-4 h-4" />
            </Link>
          )}
        </div>
      </div>
    </Card>
  )
}
