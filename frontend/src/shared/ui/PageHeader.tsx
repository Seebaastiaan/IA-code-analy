import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: ReactNode
  subtitle?: ReactNode
  eyebrow?: ReactNode
  actions?: ReactNode
}

export function PageHeader({ title, subtitle, eyebrow, actions }: PageHeaderProps) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-6">
      <div>
        {eyebrow && <p className="text-sm text-slate-500 dark:text-slate-400">{eyebrow}</p>}
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white">{title}</h1>
        {subtitle && <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-col sm:flex-row gap-2">{actions}</div>}
    </div>
  )
}
