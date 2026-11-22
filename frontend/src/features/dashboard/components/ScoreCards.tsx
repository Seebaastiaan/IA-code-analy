import { Link } from 'react-router'
import { CAT } from '@/shared/constants/categories'
import { paths } from '@/shared/constants/paths'
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

/** Reglas de negocio (solo si el análisis tuvo reglas medibles); clic → pestaña Reglas del reporte. */
export function BusinessKpiCard({ repoId, reportId, value, prev }: { repoId: string; reportId: string; value: number; prev: number | null }) {
  return (
    <Link to={paths.report(repoId, reportId, { tab: 'reglas' })} className={cn(cardClass, 'p-5 text-left hover:border-slate-300 dark:hover:border-slate-700 hover:shadow-md transition block')}>
      <div className="flex items-center gap-3">
        <span className="w-10 h-10 rounded-xl grid place-items-center bg-violet-100 text-violet-600 dark:bg-violet-500/15 dark:text-violet-300">
          <Icon name="check" />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-medium truncate">Reglas de negocio</p>
          <p className="text-xs text-slate-400">Reglas aprobadas · prueba o patrón</p>
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
        <ProgressBar value={value} className="bg-violet-500" />
      </div>
    </Link>
  )
}

/** KPI por categoría; clic → reporte filtrado por esa categoría. */
export function CategoryKpiCard({ cat, repoId, reportId, value, prev }: { cat: Category; repoId: string; reportId: string; value: number; prev: number | null }) {
  return (
    <Link to={paths.report(repoId, reportId, { cat })} className={cn(cardClass, 'p-5 text-left hover:border-slate-300 dark:hover:border-slate-700 hover:shadow-md transition block')}>
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
    </Link>
  )
}
