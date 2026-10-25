import { Card, EmptyState, ErrorState, Icon, Skeleton } from '@/shared/ui'
import { formatDateTime, formatDuration } from '@/shared/utils/format'
import { useRepoHistory } from '../api/repos.api'
import type { Repo } from '../types'
import { FindingCounts } from './FindingCounts'

/** Análisis guardados de un repo con sus hallazgos de Seguridad; el score se agrega en el Sprint 6. */
export function SavedReports({ repo }: { repo: Repo }) {
  const { data, isPending, error, refetch } = useRepoHistory(repo.id)

  return (
    <Card className="mt-6 overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800 flex flex-wrap items-center gap-2">
        <Icon name="save" className="w-4 h-4 text-slate-400" />
        <h2 className="font-semibold">Análisis guardados</h2>
        <span className="text-sm text-slate-500 truncate">· {repo.name}</span>
        <span className="ml-auto text-xs text-slate-400">Hallazgos de Bandit y pip-audit · el score se agrega a partir del Sprint 6</span>
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
                <th className="px-5 py-2.5 font-semibold">Seguridad</th>
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
                    <FindingCounts counts={r.findings} />
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
