import { CAT } from '@/shared/constants/categories'
import { TONE, tone } from '@/shared/constants/tones'
import type { Category, Scores } from '@/shared/types/common'
import { Card, Chip, DeltaBadge, Icon, ProgressBar, ScoreRing, cardClass } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'

export function GlobalScoreCard({ name, scores, prev, threshold }: { name: string; scores: Scores; prev: Scores | null; threshold: number }) {
  const passes = scores.global >= threshold
  return (
    <Card className="p-5 sm:col-span-2 xl:col-span-1 flex items-center gap-5 bg-gradient-to-br from-white to-brand-50/60 dark:from-slate-900 dark:to-brand-500/5">
      <ScoreRing value={scores.global} size={96} stroke={9} />
      <div className="min-w-0">
        <p className="text-sm font-medium">Score global</p>
        <p className="text-xs text-slate-400 mb-2 truncate">{name}</p>
        {prev ? (
          <>
            <DeltaBadge delta={scores.global - prev.global} big />
            <p className="text-xs text-slate-400 mt-0.5">vs. análisis anterior</p>
          </>
        ) : (
          <p className="text-xs text-slate-400">Primer análisis</p>
        )}
        <Chip tone={passes ? 'success' : 'danger'} className="mt-2">
          {passes ? 'Supera' : 'No supera'} el umbral ({threshold})
        </Chip>
      </div>
    </Card>
  )
}

/** KPI por categoría (el reporte filtrado por categoría llega en el Sprint 7). */
export function CategoryKpiCard({ cat, value, prev }: { cat: Category; value: number; prev: number | null }) {
  return (
    <div className={cn(cardClass, 'p-5 text-left')}>
      <div className="flex items-center gap-3">
        <span className={cn('w-10 h-10 rounded-xl grid place-items-center', CAT[cat].soft)}>
          <Icon name={CAT[cat].icon} />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-medium truncate">{CAT[cat].label}</p>
          <p className="text-xs text-slate-400">{CAT[cat].tools}</p>
        </div>
      </div>
      <div className="flex items-end justify-between mt-4">
        <p className={cn('text-3xl font-bold tabular-nums', TONE[tone(value)].text)}>
          {Math.round(value)}
          <span className="text-base text-slate-400 font-medium">/100</span>
        </p>
        {prev != null && <DeltaBadge delta={value - prev} />}
      </div>
      <div className="mt-3">
        <ProgressBar value={value} className={CAT[cat].bar} />
      </div>
    </div>
  )
}
