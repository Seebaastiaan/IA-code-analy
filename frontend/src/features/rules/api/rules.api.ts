import { queryOptions, useQuery } from '@tanstack/react-query'
import { EP } from '@/shared/api/endpoints'
import { download, http, openDocument } from '@/shared/api/http'
import type { BusinessRules, HarnessView, ImportedRules, ImportRulesRequest, ControlExpected, Concordance, DoubtAnswer, MatrixCell, PermissionMatrix, ProjectRules, RuleApproval, RulesPrecheck, RulesValidation, RuleTestsView } from '../types'

export const RULES_FILENAME = 'reglas_negocio.toml'

export const rulesApi = {
  report: (repoId: string, reportId: string) => http.get<BusinessRules>(EP.report.rules(reportId), { repo: repoId }),
  project: (repoId: string) => http.get<ProjectRules>(EP.rules.project(repoId)),
  upload: (repoId: string, content: string) => http.put<ProjectRules>(EP.rules.project(repoId), { content }),
  remove: (repoId: string) => http.delete<ProjectRules>(EP.rules.project(repoId)),
  setStates: (repoId: string, ids: string[], status: RuleApproval, by: 'equipo' | 'programa' = 'equipo') => http.post<ProjectRules>(EP.rules.states(repoId), { ids, status, by }),
  setDoubts: (repoId: string, ruleId: string, doubts: string[]) => http.put<ProjectRules>(EP.rules.doubts(repoId, ruleId), { doubts }),
  /** Contesta una duda con sí o no: la duda se cierra, la respuesta queda en la regla y el proyecto la recuerda */
  answerDoubt: (repoId: string, ruleId: string, doubt: string, answer: DoubtAnswer) => http.post<ProjectRules>(EP.rules.answer(repoId, ruleId), { doubt, answer }),
  /** «Escribe una regla con tus palabras»: la IA la redacta y se agrega en borrador */
  writeRule: (repoId: string, text: string) => http.post<ProjectRules>(EP.rules.write(repoId), { text }),
  concordance: (repoId: string) => http.get<Concordance>(EP.rules.control(repoId)),
  setExpected: (repoId: string, ruleId: string, expected: ControlExpected | null) => http.put<Concordance>(EP.rules.expected(repoId, ruleId), { expected }),
  validate: (repoId: string, content: string) => http.post<RulesValidation>(EP.rules.validate(repoId), { content }),
  /** Las reglas como documento legible: se abre en otra pestaña (imprimible a PDF) o se baja en Markdown */
  viewDocument: (repoId: string) => openDocument(EP.rules.document(repoId), { formato: 'html' }),
  downloadDocument: (repoId: string) => download(EP.rules.document(repoId), { formato: 'md' }, 'reglas_de_negocio.md'),
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
  tests: (repoId: string) => http.get<RuleTestsView>(EP.rules.tests(repoId)),
  /** Genera en segundo plano las de `ids` (sin `ids`: las reglas sin prueba o desactualizadas) */
  generateTests: (repoId: string, ids?: string[]) => http.post<RuleTestsView>(EP.rules.tests(repoId), { ids: ids ?? null }),
  /** Primera corrida en el sandbox (sin `ids`: las válidas sin correr) */
  runTests: (repoId: string, ids?: string[]) => http.post<RuleTestsView>(EP.rules.testsRun(repoId), { ids: ids ?? null }),
  approveTests: (repoId: string, ids: string[]) => http.post<RuleTestsView>(EP.rules.testsApprove(repoId), { ids }),
  editTest: (repoId: string, ruleId: string, code: string) => http.put<RuleTestsView>(EP.rules.test(repoId, ruleId), { code }),
  removeTest: (repoId: string, ruleId: string) => http.delete<RuleTestsView>(EP.rules.test(repoId, ruleId)),
  exportTests: (repoId: string, name: string) => download(EP.rules.export(repoId), {}, name),
  matrix: (repoId: string, ruleId: string) => http.get<PermissionMatrix>(EP.rules.testMatrix(repoId, ruleId)),
  /** Guarda la matriz y escribe su prueba (sin IA); `cells` = acción → rol → permitido | prohibido | null */
  saveMatrix: (repoId: string, ruleId: string, cells: Record<string, Record<string, MatrixCell | null>>) =>
    http.put<RuleTestsView>(EP.rules.testMatrix(repoId, ruleId), { cells }),
  /** La IA dice dónde parece estar implementada la regla (no cambia su estado) */
  explainRule: (repoId: string, ruleId: string) => http.post<RuleTestsView>(EP.rules.testEvidence(repoId, ruleId)),
  /** Prueba de fuerza en segundo plano (sin `ids`: las que pasan y no la tienen) */
  strengthTests: (repoId: string, ids?: string[]) => http.post<RuleTestsView>(EP.rules.testsStrength(repoId), { ids: ids ?? null }),
}

/** Bajo la clave del reporte: se refresca junto con él (re-analizar, guardar en el editor). */
export const reportRulesQuery = (repoId: string, reportId = 'latest') =>
  queryOptions({ queryKey: ['report', repoId, reportId, 'reglas'], queryFn: () => rulesApi.report(repoId, reportId) })

export const projectRulesQuery = (repoId: string) => queryOptions({ queryKey: ['rules', repoId], queryFn: () => rulesApi.project(repoId) })

export const useReportRules = (repoId: string, reportId = 'latest') => useQuery(reportRulesQuery(repoId, reportId))

export const concordanceQuery = (repoId: string) => queryOptions({ queryKey: ['rules', repoId, 'control'], queryFn: () => rulesApi.concordance(repoId) })

export const useProjectRules = (repoId: string) => useQuery({ ...projectRulesQuery(repoId), enabled: Boolean(repoId) })

export const harnessQuery = (repoId: string) => queryOptions({ queryKey: ['rules', repoId, 'arnes'], queryFn: () => rulesApi.harness(repoId) })

/** Mientras corre la prueba de humo se consulta cada 2 s. */
export const useHarness = (repoId: string) =>
  useQuery({ ...harnessQuery(repoId), enabled: Boolean(repoId), refetchInterval: (q) => (q.state.data?.harness?.smoke === 'corriendo' ? 2000 : false) })

export const ruleTestsQuery = (repoId: string) => queryOptions({ queryKey: ['rules', repoId, 'pruebas'], queryFn: () => rulesApi.tests(repoId) })

/** Mientras genera o corre en segundo plano se consulta cada 2 s. */
export const useRuleTests = (repoId: string, enabled = true) =>
  useQuery({ ...ruleTestsQuery(repoId), enabled: Boolean(repoId) && enabled, refetchInterval: (q) => (q.state.data?.busy ? 2000 : false) })
