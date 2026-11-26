import { useParams, useSearchParams } from 'react-router'
import { useReport } from '@/features/report'
import { RulesSettings } from '@/features/rules'
import { ErrorState, PageHeader, PageLoader, Tabs } from '@/shared/ui'
import { useConfig } from '../api/config.api'
import { SettingsForm } from '../components/SettingsForm'

type SettingsTab = 'general' | 'reglas'

const TABS: { value: SettingsTab; label: string }[] = [
  { value: 'general', label: 'General' },
  { value: 'reglas', label: 'Reglas de negocio' },
]

export default function SettingsPage() {
  const { repoId = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const tab: SettingsTab = params.get('tab') === 'reglas' ? 'reglas' : 'general'
  const setTab = (t: SettingsTab) =>
    setParams(
      (p) => {
        if (t === 'general') p.delete('tab')
        else p.set('tab', t)
        return p
      },
      { replace: true },
    )
  const config = useConfig(repoId)
  const { data: report } = useReport(repoId)
  const name = report?.repo_name ?? ''

  return (
    <>
      <PageHeader
        title="Configuración"
        subtitle={
          tab === 'reglas' ? (
            <>
              Reglas de negocio de <b>{name}</b>: importa el documento de requisitos y el programa las prepara y verifica.
            </>
          ) : (
            <>
              Ajustes del proyecto <b>{name}</b>. Se guardan en <code className="font-mono">.ia_voy.toml</code>.
            </>
          )
        }
      />
      <Tabs className="mb-6" options={TABS} value={tab} onChange={setTab} />
      {tab === 'reglas' ? (
        <RulesSettings repoId={repoId} />
      ) : config.error ? (
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
