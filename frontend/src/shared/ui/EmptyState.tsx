import type { ReactNode } from 'react'
import { Icon, type IconName } from './Icon'

export function EmptyState({ icon = 'search', title, children }: { icon?: IconName; title: string; children?: ReactNode }) {
  return (
    <div className="p-10 text-center">
      <span className="mx-auto w-12 h-12 rounded-2xl bg-slate-100 dark:bg-slate-800 grid place-items-center text-slate-400">
        <Icon name={icon} />
      </span>
      <p className="mt-3 font-medium">{title}</p>
      {children && <div className="mt-2 text-sm text-slate-500">{children}</div>}
    </div>
  )
}
