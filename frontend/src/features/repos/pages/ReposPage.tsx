import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { paths } from '@/shared/constants/paths'
import { EmptyState, ErrorState, Icon, Input, PageHeader, Skeleton, buttonClass } from '@/shared/ui'
import { useRepos } from '../api/repos.api'
import { RepoCard } from '../components/RepoCard'
import { SavedReports } from '../components/SavedReports'
import { useSelectedRepo } from '../store/selectedRepo.store'

export default function ReposPage() {
  const { data: repos, isPending, error, refetch } = useRepos()
  const [params] = useSearchParams()
  const [q, setQ] = useState(params.get('q') ?? '')
  const { repoId, select } = useSelectedRepo()
  const visible = repos?.filter((r) => r.name.toLowerCase().includes(q.toLowerCase())) ?? []
  // El historial se muestra para el repo activo; si no hay uno (o ya no existe), el primero con análisis
  const active = visible.find((r) => r.id === repoId) ?? visible.find((r) => r.reports > 0) ?? null

  return (
    <>
      <PageHeader
        title="Repositorios"
        subtitle={repos ? `${repos.length} repositorios conectados al equipo · ${repos.reduce((n, r) => n + r.reports, 0)} análisis guardados` : ' '}
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
        <>
          <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
            {visible.map((r) => (
              <RepoCard key={r.id} repo={r} selected={r.id === active?.id} onSelect={() => select(r.id)} />
            ))}
          </div>
          {active && <SavedReports repo={active} />}
        </>
      )}
    </>
  )
}
