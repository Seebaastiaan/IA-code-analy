import { queryOptions, useQuery } from '@tanstack/react-query'
import { EP } from '@/shared/api/endpoints'
import { download, http } from '@/shared/api/http'
import type { ExportFormat, Report } from '../types'

const EXT: Record<ExportFormat, string> = { json: 'json', html: 'html', md: 'md', sarif: 'sarif.json' }

/** reportId = 'latest' devuelve el último análisis del repo. */
export const reportQuery = (repoId: string, reportId = 'latest') =>
  queryOptions({
    queryKey: ['report', repoId, reportId],
    queryFn: () => http.get<Report>(EP.report.get(reportId), { repo: repoId }),
  })

export const useReport = (repoId: string, reportId = 'latest') => useQuery(reportQuery(repoId, reportId))

export const exportReport = (reportId: string, format: ExportFormat) =>
  download(EP.report.export(reportId), { format }, `reporte-${reportId}.${EXT[format]}`)
