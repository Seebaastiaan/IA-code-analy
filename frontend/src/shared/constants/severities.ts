import type { Severity } from '@/shared/types/common'

interface SeverityMeta {
  label: string
  chip: string
  dot: string
  /** Fondo de la línea de código afectada */
  line: string
  text: string
}

export const SEV: Record<Severity, SeverityMeta> = {
  alta: {
    label: 'Alta',
    chip: 'bg-rose-50 text-rose-700 ring-rose-600/20 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-400/30',
    dot: 'bg-rose-500',
    line: 'bg-rose-500/[.07] dark:bg-rose-500/10',
    text: 'text-rose-600 dark:text-rose-400',
  },
  media: {
    label: 'Media',
    chip: 'bg-amber-50 text-amber-700 ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-400/30',
    dot: 'bg-amber-500',
    line: 'bg-amber-500/[.07] dark:bg-amber-500/10',
    text: 'text-amber-600 dark:text-amber-400',
  },
  baja: {
    label: 'Baja',
    chip: 'bg-slate-100 text-slate-600 ring-slate-500/20 dark:bg-slate-500/10 dark:text-slate-300 dark:ring-slate-400/30',
    dot: 'bg-slate-400',
    line: 'bg-slate-500/[.06] dark:bg-slate-500/10',
    text: 'text-slate-500',
  },
}

const ORDER: Record<Severity, number> = { alta: 0, media: 1, baja: 2 }
export const bySeverity = <T extends { sev: Severity }>(a: T, b: T) => ORDER[a.sev] - ORDER[b.sev]
