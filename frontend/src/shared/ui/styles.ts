import { cn } from '@/shared/utils/cn'

/** Clases reutilizables del design system (equivalen al objeto `C` del prototipo). */

const BUTTON_VARIANTS = {
  primary:
    'gap-2 rounded-xl bg-brand-600 hover:bg-brand-700 active:bg-brand-800 text-white text-sm font-semibold px-4 py-2.5 shadow-sm shadow-brand-600/25 focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-slate-950',
  secondary:
    'gap-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 text-sm font-medium px-4 py-2.5 focus-visible:ring-2 focus-visible:ring-brand-500',
  ghost:
    'gap-1.5 rounded-lg text-sm font-medium px-2.5 py-1.5 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800',
} as const

export type ButtonVariant = keyof typeof BUTTON_VARIANTS

/** Clases del botón, para aplicarlas también a <Link>. */
export const buttonClass = (variant: ButtonVariant = 'primary', className?: string) =>
  cn('inline-flex items-center justify-center transition focus:outline-none disabled:opacity-50', BUTTON_VARIANTS[variant], className)

export const cardClass =
  'bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl shadow-sm shadow-slate-200/50 dark:shadow-none'

export const inputClass =
  'w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 px-3.5 py-2.5 text-sm outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15 transition placeholder:text-slate-400 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400 dark:disabled:bg-slate-900'

export const chipBase = 'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset'

export const CHIP_TONES = {
  neutral: 'bg-slate-100 text-slate-600 ring-slate-500/20 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700',
  success: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20 dark:bg-emerald-500/10 dark:text-emerald-300 dark:ring-emerald-400/30',
  danger: 'bg-rose-50 text-rose-700 ring-rose-600/20 dark:bg-rose-500/10 dark:text-rose-300 dark:ring-rose-400/30',
  brand: 'bg-brand-50 text-brand-700 ring-brand-600/20 dark:bg-brand-500/10 dark:text-brand-300 dark:ring-brand-400/30',
} as const
