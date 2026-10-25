import { useParams } from 'react-router'
import { PageHeader } from '@/shared/ui'
import { AnalyzeForm } from '../components/AnalyzeForm'
import { JobView } from '../components/JobView'

export default function AnalyzePage() {
  const { jobId } = useParams()
  if (jobId) return <JobView jobId={jobId} />
  return (
    <>
      <PageHeader title="Nuevo análisis" subtitle="Indica un repositorio de Python; IA voy lo clona, crea su entorno aislado y guarda el análisis en Repositorios. Otros lenguajes no se analizan." />
      <AnalyzeForm />
    </>
  )
}
