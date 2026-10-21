import { cn } from '@/shared/utils/cn'

interface ToggleProps {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
}

export function Toggle({ checked, onChange, label }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cn('relative w-11 h-6 shrink-0 rounded-full transition', checked ? 'bg-brand-600' : 'bg-slate-200 dark:bg-slate-700')}
    >
      <span className={cn('absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all', checked ? 'left-[22px]' : 'left-0.5')} />
    </button>
  )
}
