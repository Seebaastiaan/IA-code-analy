import { cn } from '@/shared/utils/cn'

interface Option<T extends string> {
  value: T
  label: string
}

interface ChoiceProps<T extends string> {
  options: Option<T>[]
  value: T
  onChange: (value: T) => void
  className?: string
}

/** Pestañas subrayadas (Hallazgos / Cobertura / Complejidad). */
export function Tabs<T extends string>({ options, value, onChange, className }: ChoiceProps<T>) {
  return (
    <div role="tablist" className={cn('flex gap-1 border-b border-slate-200 dark:border-slate-800 overflow-x-auto scroll-thin', className)}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="tab"
          aria-selected={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            'px-4 py-2.5 text-sm font-medium border-b-2 -mb-px whitespace-nowrap transition',
            value === o.value ? 'border-brand-600 text-brand-700 dark:text-brand-300' : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

/** Control segmentado (filtro de severidad). */
export function SegmentedControl<T extends string>({ options, value, onChange, className }: ChoiceProps<T>) {
  return (
    <div className={cn('inline-flex rounded-xl bg-slate-100 dark:bg-slate-800 p-1', className)}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            'px-3 py-1.5 rounded-lg text-xs font-semibold transition',
            value === o.value ? 'bg-white dark:bg-slate-950 shadow-sm text-slate-900 dark:text-white' : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
