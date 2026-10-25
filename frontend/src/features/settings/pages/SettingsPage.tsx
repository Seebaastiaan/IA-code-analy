import { useEffect } from 'react'
import { useParams } from 'react-router'
import { useRepo, useSelectedRepo } from '@/features/repos'
import { ErrorState, PageHeader, PageLoader } from '@/shared/ui'
import { useConfig } from '../api/config.api'
import { SettingsForm } from '../components/SettingsForm'

export default function SettingsPage() {
  const { repoId = '' } = useParams()
  const config = useConfig(repoId)
  const { data: repo } = useRepo(repoId)
  const name = repo?.name ?? ''
  const select = useSelectedRepo((s) => s.select)
  useEffect(() => {
    if (repoId) select(repoId)
  }, [repoId, select])

  return (
    <>
      <PageHeader
        title="Configuración"
        subtitle={
          <>
            Ajustes del proyecto <b>{name}</b>. Se guardan en <code className="font-mono">.ia_voy.toml</code> y se aplican cuando entren los analizadores y el score.
          </>
        }
      />
      {config.error ? (
        <ErrorState error={config.error} onRetry={() => void config.refetch()} />
      ) : !config.data ? (
        <PageLoader />
      ) : (
        // key: al guardar o recargar, el formulario se reinicia con los valores del servidor
        <SettingsForm key={config.dataUpdatedAt} repoId={repoId} initial={config.data} />
      )}
    </>
  )
}
