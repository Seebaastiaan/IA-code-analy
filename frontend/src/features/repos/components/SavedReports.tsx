import { Card, EmptyState, ErrorState, Icon, Skeleton } from '@/shared/ui'
import { formatDateTime, formatDuration } from '@/shared/utils/format'
import { useRepoHistory } from '../api/repos.api'
import type { Repo } from '../types'

/** Análisis guardados de un repo: el repositorio donde los siguientes sprints agregan hallazgos y score. */
export function SavedReports({ repo }: { repo: Repo }) {
  const { data, isPending, error, refetch } = useRepoHistory(repo.id)

  return (
    <Card className="mt-6 overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800 flex flex-wrap items-center gap-2">
        <Icon name="save" className="w-4 h-4 text-slate-400" />
        <h2 className="font-semibold">Análisis guardados</h2>
        <span className="text-sm text-slate-500 truncate">· {repo.name}</span>
        <span className="ml-auto text-xs text-slate-400">Los hallazgos y el score se agregan a cada análisis a partir del Sprint 5</span>
      </div>
      {error ? (
        <div className="p-5">
          <ErrorState error={error} onRetry={() => void refetch()} />
        </div>
      ) : isPending ? (
        <div className="p-5 space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-9" />
          ))}
        </div>
      ) : !data.length ? (
        <EmptyState icon="doc" title="Este repositorio todavía no tiene análisis guardados" />
      ) : (
        <div className="overflow-x-auto scroll-thin">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wider text-slate-400">
              <tr>
                <th className="px-5 py-2.5 font-semibold">#</th>
                <th className="px-3 py-2.5 font-semibold">Fecha</th>
                <th className="px-3 py-2.5 font-semibold">Rama</th>
                <th className="px-3 py-2.5 font-semibold">Commit</th>
                <th className="px-3 py-2.5 font-semibold">Lenguajes</th>
                <th className="px-3 py-2.5 font-semibold">Duración</th>
                <th className="px-5 py-2.5 font-semibold">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {data.map((r) => (
                <tr key={r.id}>
                  <td className="px-5 py-2.5 font-semibold tabular-nums">#{r.num}</td>
                  <td className="px-3 py-2.5 text-slate-500 whitespace-nowrap">{formatDateTime(r.created_at)}</td>
                  <td className="px-3 py-2.5 font-mono text-xs">{r.branch}</td>
                  <td className="px-3 py-2.5 font-mono text-xs">{r.commit}</td>
                  <td className="px-3 py-2.5 text-xs text-slate-500">{r.languages.map((l) => `${l.name} ${l.files}`).join(' · ') || '—'}</td>
                  <td className="px-3 py-2.5 tabular-nums text-slate-500">{formatDuration(r.duration_s)}</td>
                  <td className="px-5 py-2.5">
                    <span className="inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-[11px] font-medium bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300">
                      <Icon name="check" className="w-3 h-3" />
                      Entorno listo
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}
