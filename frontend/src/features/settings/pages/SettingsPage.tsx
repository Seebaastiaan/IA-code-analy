import { useParams } from 'react-router'
import { useReport } from '@/features/report'
import { ErrorState, PageHeader, PageLoader } from '@/shared/ui'
import { useConfig } from '../api/config.api'
import { SettingsForm } from '../components/SettingsForm'

export default function SettingsPage() {
  const { repoId = '' } = useParams()
  const config = useConfig(repoId)
  const { data: report } = useReport(repoId)
  const name = report?.repo_name ?? ''

  return (
    <>
      <PageHeader
        title="Configuración"
        subtitle={
          <>
            Ajustes del proyecto <b>{name}</b>. Se guardan en <code className="font-mono">.ia_voy.toml</code>.
          </>
        }
      />
      {config.error ? (
        <ErrorState error={config.error} onRetry={() => void config.refetch()} />
      ) : !config.data ? (
        <PageLoader />
      ) : (
        // key: al guardar o recargar, el formulario se reinicia con los valores del servidor
        <SettingsForm
          key={config.dataUpdatedAt}
          repoId={repoId}
          repoName={name}
          initial={config.data}
          categoryScores={report ? { seg: report.scores.seg, test: report.scores.test, prac: report.scores.prac } : null}
        />
      )}
    </>
  )
}
