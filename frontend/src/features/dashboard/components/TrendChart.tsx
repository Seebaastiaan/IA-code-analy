import { useState } from 'react'
import { CAT } from '@/shared/constants/categories'
import { BRAND_HEX } from '@/shared/constants/tones'
import { cn } from '@/shared/utils/cn'
import { f1 } from '@/shared/utils/score'
import type { HistoryPoint } from '../types'

type SeriesKey = 'global' | 'seg' | 'test' | 'prac'

const SERIES: { key: SeriesKey; label: string; color: string }[] = [
  { key: 'global', label: 'Global', color: BRAND_HEX },
  { key: 'seg', label: CAT.seg.label, color: CAT.seg.hex },
  { key: 'test', label: CAT.test.label, color: CAT.test.hex },
  { key: 'prac', label: CAT.prac.label, color: CAT.prac.hex },
]

const W = 640
const H = 230
const PAD = { l: 34, r: 14, t: 14, b: 30 }
const fmtDate = (d: string) => new Intl.DateTimeFormat('es', { day: '2-digit', month: 'short' }).format(new Date(d))

/** Tendencia por análisis. Tocar la leyenda oculta o muestra cada serie. */
export function TrendChart({ history }: { history: HistoryPoint[] }) {
  const [hidden, setHidden] = useState<Set<SeriesKey>>(new Set())
  const visible = SERIES.filter((s) => !hidden.has(s.key))
  const values = visible.flatMap((s) => history.map((h) => h[s.key]))
  const lo = Math.max(0, Math.floor((Math.min(...(values.length ? values : [40])) - 5) / 10) * 10)
  const n = Math.max(history.length - 1, 1)
  const x = (i: number) => PAD.l + (i * (W - PAD.l - PAD.r)) / n
  const y = (v: number) => PAD.t + (1 - (v - lo) / (100 - lo)) * (H - PAD.t - PAD.b)
  const ticks: number[] = []
  for (let v = lo; v <= 100; v += lo <= 40 ? 20 : 10) ticks.push(v)

  const toggle = (k: SeriesKey) =>
    setHidden((prev) => {
      const next = new Set(prev)
      if (next.has(k)) next.delete(k)
      else next.add(k)
      return next
    })

  const points = (k: SeriesKey) => history.map((h, i) => `${x(i)},${y(h[k])}`).join(' ')

  return (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="Tendencia de puntuación">
        <defs>
          <linearGradient id="trend-area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={BRAND_HEX} stopOpacity=".22" />
            <stop offset="1" stopColor={BRAND_HEX} stopOpacity="0" />
          </linearGradient>
        </defs>
        {ticks.map((v) => (
          <g key={v}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} className="stroke-slate-100 dark:stroke-slate-800" strokeWidth={1} />
            <text x={PAD.l - 8} y={y(v) + 4} textAnchor="end" className="fill-slate-400" fontSize={11}>
              {v}
            </text>
          </g>
        ))}
        {history.map((h, i) => (
          <text key={h.date} x={x(i)} y={H - 8} textAnchor="middle" className="fill-slate-400" fontSize={11}>
            {fmtDate(h.date)}
          </text>
        ))}
        {!hidden.has('global') && history.length > 1 && <polygon points={`${x(0)},${y(lo)} ${points('global')} ${x(history.length - 1)},${y(lo)}`} fill="url(#trend-area)" />}
        {[...visible].reverse().map((s) => {
          const g = s.key === 'global'
          return (
            <g key={s.key}>
              <polyline points={points(s.key)} fill="none" stroke={s.color} strokeWidth={g ? 3 : 2} strokeLinejoin="round" strokeLinecap="round" opacity={g ? 1 : 0.85} />
              {history.map((h, i) => (
                <circle key={i} cx={x(i)} cy={y(h[s.key])} r={g ? 4.5 : 3} fill={s.color} className="stroke-white dark:stroke-slate-900" strokeWidth={2}>
                  <title>{`${fmtDate(h.date)} · ${s.label}: ${f1(h[s.key])}`}</title>
                </circle>
              ))}
            </g>
          )
        })}
      </svg>
      <div className="flex flex-wrap gap-2 mt-3">
        {SERIES.map((s) => (
          <button
            key={s.key}
            type="button"
            aria-pressed={!hidden.has(s.key)}
            onClick={() => toggle(s.key)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium border transition',
              hidden.has(s.key) ? 'border-slate-200 dark:border-slate-800 text-slate-400 line-through' : 'border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800',
            )}
          >
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: s.color }} />
            {s.label}
          </button>
        ))}
      </div>
    </>
  )
}
