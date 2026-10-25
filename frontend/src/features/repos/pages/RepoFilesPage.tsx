import { useEffect } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { ApiError } from '@/shared/api/errors'
import { Card, CodeSnippet, EmptyState, ErrorState, Icon, PageHeader, PageLoader } from '@/shared/ui'
import { useFile, useRepo, useRepoTree } from '../api/repos.api'
import { FolderTree } from '../components/FolderTree'
import { useSelectedRepo } from '../store/selectedRepo.store'

// Más líneas que esto vuelven lenta la página sin aportar al recorrido del código
const MAX_LINES = 3000

/** Carpetas y archivos de texto del último clon del repositorio, en solo lectura. */
export default function RepoFilesPage() {
  const { repoId = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const { data: repo } = useRepo(repoId)
  const tree = useRepoTree(repoId)

  const selectRepo = useSelectedRepo((s) => s.select)
  // Abrir los archivos de un repo lo vuelve el repo activo (Configuración del sidebar)
  useEffect(() => {
    if (repoId) selectRepo(repoId)
  }, [repoId, selectRepo])

  const path = params.get('file') ?? tree.data?.find((e) => e.path.endsWith('.py'))?.path ?? tree.data?.[0]?.path ?? null
  const file = useFile(repoId, path)
  const select = (p: string) => setParams({ file: p })

  const header = (
    <PageHeader
      title={repo?.name ?? 'Archivos'}
      subtitle={
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {repo && (
            <span className="flex items-center gap-1">
              <Icon name="branch" className="w-3.5 h-3.5" />
              {repo.branch}
              {repo.commit && <span className="font-mono">· {repo.commit}</span>}
            </span>
          )}
          {tree.data && <span>{tree.data.filter((e) => e.path.endsWith('.py')).length} archivos .py · {tree.data.length} en total</span>}
        </span>
      }
    />
  )

  if (tree.error) {
    const notCloned = tree.error instanceof ApiError && tree.error.code === 'not_cloned'
    return (
      <>
        {header}
        {notCloned ? (
          <EmptyState icon="folder" title="Este repositorio aún no se ha clonado">
            <p>Vuelve a analizarlo desde Repositorios para descargar su código.</p>
          </EmptyState>
        ) : (
          <ErrorState error={tree.error} onRetry={() => void tree.refetch()} />
        )}
      </>
    )
  }
  if (tree.isPending) return <PageLoader />
  if (!tree.data.length)
    return (
      <>
        {header}
        <EmptyState icon="file" title="El repositorio no tiene archivos de texto" />
      </>
    )

  const lines = file.data?.content.split('\n') ?? []
  return (
    <>
      {header}
      <div className="grid lg:grid-cols-[18rem_1fr] gap-4">
        <Card className="p-2 h-fit lg:max-h-[calc(100vh-12rem)] lg:sticky lg:top-20 overflow-y-auto scroll-thin">
          <FolderTree entries={tree.data} active={path} onSelect={select} />
        </Card>

        <Card className="min-w-0 overflow-hidden">
          <div className="px-4 py-2.5 border-b border-slate-200 dark:border-slate-800 flex items-center gap-2">
            <Icon name="file" className="w-4 h-4 text-slate-400" />
            <span className="font-mono text-sm font-medium truncate">{path}</span>
            {file.data && <span className="ml-auto shrink-0 text-xs text-slate-400">{lines.length} líneas</span>}
          </div>
          <div className="p-3">
            {file.error ? (
              <ErrorState error={file.error} onRetry={() => void file.refetch()} />
            ) : !file.data ? (
              <PageLoader />
            ) : (
              <>
                <CodeSnippet lines={lines.slice(0, MAX_LINES).map((text, i) => ({ line: i + 1, text }))} />
                {lines.length > MAX_LINES && <p className="mt-2 text-xs text-slate-400">Se muestran las primeras {MAX_LINES} líneas de {lines.length}.</p>}
              </>
            )}
          </div>
        </Card>
      </div>
    </>
  )
}
