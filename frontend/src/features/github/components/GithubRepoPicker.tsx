import { useEffect, useState } from 'react'
import { GithubMark, useGithubLogin } from '@/features/auth'
import { ApiError } from '@/shared/api/errors'
import { paths } from '@/shared/constants/paths'
import { Button, Chip, Icon, Input, Skeleton, Spinner } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import { timeAgo } from '@/shared/utils/format'
import { useGithubRepos, useGithubStatus } from '../api/github.api'
import type { GithubRepo } from '../types'

/** Vuelve a pasar por GitHub (sin cerrar la sesión de la app) cuando el token se revocó o venció. */
function ReconnectButton() {
  const login = useGithubLogin(paths.analyze())
  const busy = login.isPending || login.isSuccess
  return (
    <Button variant="secondary" onClick={() => login.mutate()} disabled={busy}>
      {busy ? <Spinner /> : <GithubMark className="w-4 h-4" />}
      Volver a conectar GitHub
    </Button>
  )
}

function RepoRow({ repo, selected, onSelect }: { repo: GithubRepo; selected: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        'w-full flex items-start gap-3 px-3.5 py-2.5 text-left hover:bg-slate-50 dark:hover:bg-slate-800/40',
        selected && 'bg-brand-50 hover:bg-brand-50 dark:bg-brand-500/10 dark:hover:bg-brand-500/10',
      )}
    >
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span className="font-mono text-[13px] font-medium truncate">{repo.full_name}</span>
          {repo.private && (
            <Chip>
              <Icon name="lock" className="w-3 h-3" />
              Privado
            </Chip>
          )}
        </span>
        {repo.description && <span className="block text-xs text-slate-500 truncate">{repo.description}</span>}
      </span>
      <span className="shrink-0 text-xs text-slate-400">{timeAgo(repo.pushed_at)}</span>
      {selected && <Icon name="check" className="w-4 h-4 shrink-0 text-brand-600 dark:text-brand-300" />}
    </button>
  )
}

/**
 * Origen del análisis desde la cuenta de GitHub con la que se inició sesión: lista sus repos
 * (incluidos privados) y avisa al formulario del repo elegido.
 */
export function GithubRepoPicker({ selected, onSelect }: { selected: string | null; onSelect: (repo: GithubRepo) => void }) {
  const status = useGithubStatus()
  const connected = Boolean(status.data?.connected)

  const [search, setSearch] = useState('')
  const [q, setQ] = useState('')
  useEffect(() => {
    const t = setTimeout(() => setQ(search.trim()), 300)
    return () => clearTimeout(t)
  }, [search])
  const repos = useGithubRepos(q, connected)
  // El backend descarta el token si GitHub lo revocó (409): se ofrece reconectar
  const lost = !connected || (repos.error instanceof ApiError && repos.error.code === 'github_not_connected')

  if (status.isPending) return <Skeleton className="h-16" />

  if (lost)
    return (
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 rounded-xl border border-dashed border-slate-300 dark:border-slate-700 p-4">
        <div className="flex-1 text-sm">
          <p className="font-medium">Tus repositorios de GitHub no están disponibles</p>
          <p className="text-xs text-slate-500">
            {status.isError ? `No se pudo consultar GitHub: ${status.error.message}` : 'GitHub ya no da acceso a IA voy. Vuelve a autorizarlo, o escribe la URL abajo.'}
          </p>
        </div>
        <ReconnectButton />
      </div>
    )

  const { login, avatar_url } = status.data!
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
      <div className="flex items-center gap-3 px-3.5 py-2.5 border-b border-slate-100 dark:border-slate-800">
        {avatar_url ? <img src={avatar_url} alt="" className="w-7 h-7 rounded-full" /> : <GithubMark className="w-6 h-6 text-slate-500" />}
        <p className="text-sm flex-1 min-w-0 truncate">
          Repositorios de <span className="font-medium">@{login}</span>
        </p>
      </div>
      <div className="p-3 border-b border-slate-100 dark:border-slate-800">
        <Input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Buscar repositorio…" aria-label="Buscar repositorio de GitHub" />
      </div>
      <div className="max-h-64 overflow-y-auto divide-y divide-slate-100 dark:divide-slate-800">
        {repos.isPending ? (
          <div className="grid place-items-center py-8 text-slate-400">
            <Spinner className="w-5 h-5" />
          </div>
        ) : repos.isError ? (
          <p className="px-3.5 py-6 text-center text-sm text-rose-600 dark:text-rose-400">{repos.error.message}</p>
        ) : !repos.data.length ? (
          <p className="px-3.5 py-6 text-center text-sm text-slate-500">{q ? `Ningún repositorio coincide con "${q}"` : 'Tu cuenta no tiene repositorios'}</p>
        ) : (
          repos.data.map((r) => <RepoRow key={r.full_name} repo={r} selected={r.full_name === selected} onSelect={() => onSelect(r)} />)
        )}
      </div>
    </div>
  )
}
