import { Link } from 'react-router'
import { CAT } from '@/shared/constants/categories'
import { paths } from '@/shared/constants/paths'
import { TONE, tone } from '@/shared/constants/tones'
import { CATEGORIES, type Category, type Severity } from '@/shared/types/common'
import { Button, Card, Chip, DeltaBadge, Icon, ProgressBar, ScoreRing, buttonClass } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import { formatDateTime, formatDuration } from '@/shared/utils/format'
import { f1, weightSum } from '@/shared/utils/score'
import type { CatFilter } from '../hooks/useReportFilters'
import type { Report } from '../types'

interface ReportHeaderProps {
  report: Report
  cat: CatFilter
  onCat: (cat: CatFilter) => void
  onShare: () => void
}

export function ReportHeader({ report: r, cat, onCat, onShare }: ReportHeaderProps) {
  const open = r.findings.filter((f) => f.status === 'open')
  const count = (s: Severity) => open.filter((f) => f.sev === s).length
  const sum = weightSum(r.weights) || 1
  const w = (k: Category) => (r.weights[k] / sum).toFixed(2)
  // IA voy analiza solo Python: se avisa qué más trae el repo (el resto no entra al score)
  const python = r.languages.find((l) => l.name === 'Python')?.files ?? 0
  const others = r.languages.filter((l) => l.name !== 'Python')

  const catNote = (k: Category) =>
    k === 'seg'
      ? `${open.filter((f) => f.cat === 'seg').length} hallazgos abiertos`
      : k === 'test'
        ? `${r.summary.coverage_total === null ? 'Cobertura no medida' : `Cobertura ${r.summary.coverage_total} %`} · ${r.analyzers.includes('pytest') ? `${r.summary.tests_failed} prueba(s) fallan` : 'pytest no se corrió'}`
        : `Complejidad media ${r.summary.avg_complexity}`

  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-col md:flex-row md:items-center gap-5">
        <ScoreRing value={r.scores.global} size={112} stroke={10} />
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight">{r.repo_name}</h1>
            <Chip>
              <Icon name="branch" className="w-3 h-3" />
              {r.branch}
            </Chip>
            {r.scores.global < r.thresholds.score && <Chip tone="danger">Bajo el umbral ({r.thresholds.score})</Chip>}
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Commit <span className="font-mono">{r.commit}</span> · {formatDateTime(r.created_at)} · {formatDuration(r.duration_s)}
          </p>
          {others.length > 0 && (
            <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">
              Solo se analiza Python ({python} archivo(s)). También tiene: {others.map((l) => `${l.name} ${l.files}`).join(' · ')}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-3 mt-3 text-sm">
            {r.prev && (
              <>
                <DeltaBadge delta={r.scores.global - r.prev.scores.global} big />
                <span className="text-slate-400">vs. #{r.prev.num}</span>
                <span className="text-slate-300 dark:text-slate-700">|</span>
              </>
            )}
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-rose-500" />
              {count('alta')} altas
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-amber-500" />
              {count('media')} medias
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-slate-400" />
              {count('baja')} bajas
            </span>
          </div>
        </div>
        <div className="grid grid-cols-2 sm:flex gap-2">
          <Button className="col-span-2 sm:col-span-1" onClick={onShare}>
            <Icon name="share" className="w-4 h-4" />
            Compartir
          </Button>
          <Link to={paths.assistant(r.repo_id)} className={buttonClass('secondary')}>
            <Icon name="chat" className="w-4 h-4" />
            Preguntar
          </Link>
          <Link to={paths.compare(r.repo_id)} className={buttonClass('secondary')}>
            <Icon name="compare" className="w-4 h-4" />
            Comparar
          </Link>
        </div>
      </div>

      <div className="mt-5 pt-5 border-t border-slate-100 dark:border-slate-800 grid sm:grid-cols-3 gap-3">
        {CATEGORIES.map((k) => {
          const active = cat === k
          const v = r.scores[k]
          return (
            <button
              key={k}
              type="button"
              aria-pressed={active}
              onClick={() => onCat(active ? 'todas' : k)}
              className={cn(
                'text-left rounded-xl border p-4 transition',
                active ? 'border-brand-400 ring-4 ring-brand-500/10 bg-brand-50/40 dark:bg-brand-500/5' : 'border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700',
              )}
            >
              <div className="flex items-center gap-2">
                <span className={cn('w-8 h-8 rounded-lg grid place-items-center', CAT[k].soft)}>
                  <Icon name={CAT[k].icon} className="w-4 h-4" />
                </span>
                <span className="text-sm font-medium">{CAT[k].label}</span>
                <span className={cn('ml-auto text-xl font-bold tabular-nums', TONE[tone(v)].text)}>{v}</span>
              </div>
              <div className="mt-3">
                <ProgressBar value={v} className={CAT[k].bar} />
              </div>
              <p className="text-xs text-slate-500 mt-2">
                {catNote(k)} · peso {Math.round((r.weights[k] / sum) * 100)}%
              </p>
            </button>
          )
        })}
      </div>
      <p className="mt-4 font-mono text-xs text-slate-500 bg-slate-50 dark:bg-slate-950 rounded-lg px-3 py-2 overflow-x-auto whitespace-nowrap scroll-thin">
        Score = {w('seg')} × {r.scores.seg} + {w('test')} × {r.scores.test} + {w('prac')} × {r.scores.prac} ={' '}
        <b className={TONE[tone(r.scores.global)].text}>{f1(r.scores.global)}</b>
      </p>
    </Card>
  )
}
