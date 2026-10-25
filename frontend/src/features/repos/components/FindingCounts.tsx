import { cn } from '@/shared/utils/cn'
import type { FindingCounts as Counts } from '../types'

const SEV: { key: keyof Counts; label: string; dot: string }[] = [
  { key: 'alta', label: 'altas', dot: 'bg-rose-500' },
  { key: 'media', label: 'medias', dot: 'bg-amber-500' },
  { key: 'baja', label: 'bajas', dot: 'bg-slate-400' },
]

/** Hallazgos de Seguridad (Bandit y pip-audit) de un análisis, por severidad. */
export function FindingCounts({ counts, className }: { counts: Counts; className?: string }) {
  if (!(counts.alta + counts.media + counts.baja)) return <span className={cn('text-xs text-emerald-600 dark:text-emerald-400', className)}>Sin hallazgos</span>
  return (
    <span className={cn('inline-flex items-center gap-2.5 text-xs whitespace-nowrap', className)}>
      {SEV.map((s) => (
        <span key={s.key} className={cn('inline-flex items-center gap-1', !counts[s.key] && 'text-slate-400')}>
          <span className={cn('w-1.5 h-1.5 rounded-full', counts[s.key] ? s.dot : 'bg-slate-300 dark:bg-slate-600')} />
          <span className="tabular-nums font-medium">{counts[s.key]}</span> {s.label}
        </span>
      ))}
    </span>
  )
}
