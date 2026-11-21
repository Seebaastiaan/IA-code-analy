import { queryOptions, useQuery } from '@tanstack/react-query'
import { EP } from '@/shared/api/endpoints'
import { download, http } from '@/shared/api/http'
import type { BusinessRules, HarnessView, ImportedRules, ImportRulesRequest, ProjectRules, RulesPrecheck, RulesValidation } from '../types'

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
  /** La IA saca las reglas de un documento de requisitos; devuelve el TOML para revisarlo (no guarda nada) */
  importDocument: (body: ImportRulesRequest) => http.post<ImportedRules>(EP.rules.import, body),
  harness: (repoId: string) => http.get<HarnessView>(EP.rules.harness(repoId)),
  /** La IA propone el arnés con el mapa y el código del proyecto (reemplaza al anterior) */
  proposeHarness: (repoId: string) => http.post<HarnessView>(EP.rules.harness(repoId)),
  harnessFromRepo: (repoId: string) => http.post<HarnessView>(EP.rules.harnessFromRepo(repoId)),
  editHarness: (repoId: string, code: string) => http.put<HarnessView>(EP.rules.harness(repoId), { code }),
  removeHarness: (repoId: string) => http.delete<HarnessView>(EP.rules.harness(repoId)),
  /** Corre la prueba de humo en el sandbox; responde enseguida con `smoke = corriendo` */
  runSmoke: (repoId: string) => http.post<HarnessView>(EP.rules.harnessSmoke(repoId)),
  approveHarness: (repoId: string) => http.post<HarnessView>(EP.rules.harnessApprove(repoId)),
}

/** Bajo la clave del reporte: se refresca junto con él (re-analizar, guardar en el editor). */
export const reportRulesQuery = (repoId: string, reportId = 'latest') =>
  queryOptions({ queryKey: ['report', repoId, reportId, 'reglas'], queryFn: () => rulesApi.report(repoId, reportId) })

export const projectRulesQuery = (repoId: string) => queryOptions({ queryKey: ['rules', repoId], queryFn: () => rulesApi.project(repoId) })

export const useReportRules = (repoId: string, reportId = 'latest') => useQuery(reportRulesQuery(repoId, reportId))

export const useProjectRules = (repoId: string) => useQuery({ ...projectRulesQuery(repoId), enabled: Boolean(repoId) })

export const harnessQuery = (repoId: string) => queryOptions({ queryKey: ['rules', repoId, 'arnes'], queryFn: () => rulesApi.harness(repoId) })

/** Mientras corre la prueba de humo se consulta cada 2 s. */
export const useHarness = (repoId: string) =>
  useQuery({ ...harnessQuery(repoId), enabled: Boolean(repoId), refetchInterval: (q) => (q.state.data?.harness?.smoke === 'corriendo' ? 2000 : false) })
