import { queryOptions, useQuery } from '@tanstack/react-query'
import { EP } from '@/shared/api/endpoints'
import { download, http } from '@/shared/api/http'
import type { BusinessRules, ProjectRules, RulesPrecheck, RulesValidation } from '../types'

export const RULES_FILENAME = 'reglas_negocio.toml'

export const rulesApi = {
  report: (repoId: string, reportId: string) => http.get<BusinessRules>(EP.report.rules(reportId), { repo: repoId }),
  project: (repoId: string) => http.get<ProjectRules>(EP.rules.project(repoId)),
  upload: (repoId: string, content: string) => http.put<ProjectRules>(EP.rules.project(repoId), { content }),
  remove: (repoId: string) => http.delete<ProjectRules>(EP.rules.project(repoId)),
  validate: (repoId: string, content: string) => http.post<RulesValidation>(EP.rules.validate(repoId), { content }),
  template: (repoId: string) => download(EP.rules.template(repoId), {}, RULES_FILENAME),
  /** `content` = valida ese texto contra el repo en vez de leer su archivo */
  precheck: (url: string, branch: string, content?: string) => http.post<RulesPrecheck>(EP.rules.precheck, { url, branch, content }),
}

/** Bajo la clave del reporte: se refresca junto con él (re-analizar, guardar en el editor). */
export const reportRulesQuery = (repoId: string, reportId = 'latest') =>
  queryOptions({ queryKey: ['report', repoId, reportId, 'reglas'], queryFn: () => rulesApi.report(repoId, reportId) })

export const projectRulesQuery = (repoId: string) => queryOptions({ queryKey: ['rules', repoId], queryFn: () => rulesApi.project(repoId) })

export const useReportRules = (repoId: string, reportId = 'latest') => useQuery(reportRulesQuery(repoId, reportId))

export const useProjectRules = (repoId: string) => useQuery({ ...projectRulesQuery(repoId), enabled: Boolean(repoId) })
