import { useState, type FormEvent } from 'react'
import { useMatches, useNavigate } from 'react-router'
import { JobPill } from '@/features/analysis'
import { useSelectedRepo } from '@/features/repos/store/selectedRepo.store'
import { paths } from '@/shared/constants/paths'
import { Icon, ThemeToggle } from '@/shared/ui'
import { UserMenu } from './UserMenu'

function usePageTitle() {
  const matches = useMatches()
  const match = [...matches].reverse().find((m) => (m.handle as { title?: string } | undefined)?.title)
  return (match?.handle as { title: string } | undefined)?.title ?? 'IA voy'
}

/** Enter → reporte del repo activo filtrado por el texto. */
function GlobalSearch() {
  const [q, setQ] = useState('')
  const navigate = useNavigate()
  const repoId = useSelectedRepo((s) => s.repoId)

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!q.trim()) return
    navigate(repoId ? `${paths.report(repoId)}?tab=hallazgos&q=${encodeURIComponent(q.trim())}` : paths.repos())
    setQ('')
  }

  return (
    <form onSubmit={onSubmit} className="hidden md:flex flex-1 max-w-md ml-6 relative" role="search">
      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
        <Icon name="search" className="w-4 h-4" />
      </span>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        aria-label="Buscar"
        placeholder="Buscar archivo, regla o hallazgo… (Enter)"
        className="w-full rounded-xl bg-slate-100 dark:bg-slate-900 border border-transparent focus:border-brand-400 focus:bg-white dark:focus:bg-slate-900 focus:ring-4 focus:ring-brand-500/10 pl-9 pr-3 py-2 text-sm outline-none transition placeholder:text-slate-400"
      />
    </form>
  )
}

export function TopBar({ onOpenMenu }: { onOpenMenu: () => void }) {
  const title = usePageTitle()
  return (
    <header className="sticky top-0 z-20 h-16 bg-white/80 dark:bg-slate-950/80 backdrop-blur border-b border-slate-200 dark:border-slate-800">
      <div className="h-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center gap-3">
        <button type="button" className="lg:hidden p-2 -ml-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800" onClick={onOpenMenu} aria-label="Abrir menú">
          <Icon name="menu" />
        </button>
        <p className="font-semibold truncate">{title}</p>
        <GlobalSearch />
        <div className="ml-auto flex items-center gap-1.5">
          <JobPill />
          <ThemeToggle />
          <UserMenu />
        </div>
      </div>
    </header>
  )
}
