import { TONE, tone } from '@/shared/constants/tones'
import { cn } from '@/shared/utils/cn'
import { f1 } from '@/shared/utils/score'

interface ScoreRingProps {
  value: number
  size?: number
  stroke?: number
  className?: string
}

/** Anillo de score coloreado por tono. Muestra un decimal en tamaños grandes. */
export function ScoreRing({ value, size = 64, stroke = 7, className }: ScoreRingProps) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const t = TONE[tone(value)]
  return (
    <div className={cn('relative shrink-0', className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" role="img" aria-label={`Score ${f1(value)}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} className="stroke-slate-100 dark:stroke-slate-800" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={t.hex}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - value / 100)}
          style={{ transition: 'stroke-dashoffset .8s ease' }}
        />
      </svg>
      <div className={cn('absolute inset-0 grid place-items-center font-bold tabular-nums', t.text)} style={{ fontSize: Math.round(size * 0.27) }}>
        {size > 80 ? f1(value) : Math.round(value)}
      </div>
    </div>
  )
}

export function DeltaBadge({ delta, big }: { delta: number; big?: boolean }) {
  if (Math.abs(delta) < 0.05) return <span className="text-xs text-slate-400">sin cambios</span>
  const up = delta > 0
  return (
    <span
      className={cn(
        'inline-flex items-center gap-0.5 font-semibold',
        big ? 'text-sm' : 'text-xs',
        up ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400',
      )}
    >
      {up ? '▲' : '▼'} {f1(Math.abs(delta))}
    </span>
  )
}

export function ProgressBar({ value, className }: { value: number; className: string }) {
  return (
    <div className="h-1.5 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
      <div className={cn('h-full rounded-full', className)} style={{ width: `${value}%` }} />
    </div>
  )
}
