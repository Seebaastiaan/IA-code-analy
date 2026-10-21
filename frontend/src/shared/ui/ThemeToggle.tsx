import { useTheme } from '@/shared/hooks/useTheme'
import { cn } from '@/shared/utils/cn'
import { Icon } from './Icon'

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggle } = useTheme()
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label="Cambiar tema"
      title="Cambiar tema claro/oscuro"
      className={cn('p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400', className)}
    >
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
    </button>
  )
}
