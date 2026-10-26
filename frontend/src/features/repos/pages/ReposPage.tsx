import { useState } from 'react'
import { Link } from 'react-router'
import { paths } from '@/shared/constants/paths'
import { EmptyState, ErrorState, Icon, Input, PageHeader, Skeleton, buttonClass } from '@/shared/ui'
import { useRepos } from '../api/repos.api'
import { RepoCard } from '../components/RepoCard'

export default function ReposPage() {
  const { data: repos, isPending, error, refetch } = useRepos()
  const [q, setQ] = useState('')
  const visible = repos?.filter((r) => r.name.toLowerCase().includes(q.toLowerCase())) ?? []

  return (
    <>
      <PageHeader
        title="Repositorios"
        subtitle={repos ? `${repos.length} repositorios conectados al equipo` : ' '}
        actions={
          <div className="flex gap-2">
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filtrar por nombre…" aria-label="Filtrar por nombre" className="sm:w-64" />
            <Link to={paths.analyze()} className={buttonClass('primary', 'shrink-0')}>
              <Icon name="plus" className="w-4 h-4" />
              <span className="hidden sm:inline">Agregar</span>
            </Link>
          </div>
        }
      />
      {error ? (
        <ErrorState error={error} onRetry={() => void refetch()} />
      ) : isPending ? (
        <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-56" />
          ))}
        </div>
      ) : !repos.length ? (
        <EmptyState icon="folder" title="Aún no hay repositorios">
          <Link to={paths.analyze()} className={buttonClass('primary', 'mt-3')}>
            Analizar el primero
          </Link>
        </EmptyState>
      ) : !visible.length ? (
        <EmptyState title="Ningún repositorio coincide con el filtro" />
      ) : (
        <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {visible.map((r) => (
            <RepoCard key={r.id} repo={r} />
          ))}
        </div>
      )}
    </>
  )
}
