import type { Severity } from '@/shared/types/common'

/** Reglas de negocio del proyecto (backend/app/analyses/reglas.py, docs/adr/ADR-003-reglas-de-negocio.md). */

/** docs/PROPUESTA_REGLAS_VERIFICABLES.md §9 */
export type RuleStatus = 'cumple' | 'no_cumple' | 'prueba_rota' | 'no_implementada' | 'sin_verificar' | 'fuera_del_codigo'
/** Cómo se verificó la regla */
export type RuleLevel = 'pruebas' | 'patron' | 'pruebas_y_patron' | 'ninguno'
/** passed…not_run: corrió en el sandbox (plugin ia_voy_reglas); sin_ejecutar: se encontró leyendo el código */
/** broken = falló por otra cosa que un assert (preparar, un fixture, un import): la prueba está rota, no el código */
export type TestOutcome = 'passed' | 'failed' | 'broken' | 'error' | 'skipped' | 'not_run' | 'sin_ejecutar'
export type RulesOrigin = 'repo' | 'app'

export interface RuleEvidence {
  file: string
  line: number
  text: string
}

export interface RuleTest {
  /** nodeid de pytest: archivo::función */
  name: string
  file: string
  line: number
  outcome: TestOutcome
  message: string
}

export interface BusinessRuleResult {
  id: string
  title: string
  description: string
  severity: Severity
  paths: string[]
  forbidden: string | null
  required: string | null
  story: string | null
  owner: string | null
  criterion: string | null
  status: RuleStatus
  level: RuleLevel
  detail: string
  evidence: RuleEvidence[]
  /** Coincidencias del patrón en total (evidence trae las primeras 20) */
  evidence_total: number
  /** Las que fallan primero */
  tests: RuleTest[]
  /** Estado en el análisis anterior (null = no había o la regla es nueva) */
  previous_status?: RuleStatus | null
}

export interface BusinessRules {
  report_id: string
  /** false = análisis anterior a las reglas de negocio */
  checked: boolean
  /** Archivo leído; null = no hay reglas declaradas */
  source: string | null
  origin: RulesOrigin | null
  project: string | null
  /** El archivo no es válido: no hay resultados */
  error: string | null
  /** El archivo del repo no era válido y se usaron las reglas corregidas en la app (origin = 'app') */
  repo_error?: string | null
  /** Las pruebas corrieron en el sandbox */
  tests_ran: boolean
  warnings: string[]
  summary: { total: number; cumple: number; no_cumple: number; sin_verificar: number; prueba_rota: number; no_implementada: number; fuera_del_codigo: number }
  rules: BusinessRuleResult[]
  /** Número del análisis anterior con el que se compara (null = es el primero con reglas) */
  previous_num?: number | null
  /** Reglas que se cumplían en el análisis anterior y ahora no */
  regressions?: string[]
}

export interface RulePreview {
  id: string
  title: string
  severity: Severity
  /** Tiene `prohibido` u `obligatorio` */
  pattern: boolean
  /** Formato v2 (docs/PROPUESTA_REGLAS_VERIFICABLES.md §5): lo que muestra la tabla de aprobación */
  description?: string
  tipo?: RuleKind | null
  /** Solo las aprobadas se verifican; lo importado entra como borrador */
  status?: RuleApproval
  source?: string | null
  /** Ambigüedades abiertas: con alguna no se puede aprobar */
  doubts?: string[]
  scenarios?: RuleScenario[]
  /** Frase del documento de requisitos que respalda la regla */
  quote?: string | null
  /** El programa la encontró en el documento (null = no se pudo comprobar, p. ej. en un PDF) */
  quote_ok?: boolean | null
  /** 'programa' = la aprobó el programa solo (se revierte en un clic); null = el equipo */
  approved_by?: 'programa' | null
}

export type RuleKind = 'datos' | 'flujo' | 'calculo' | 'permisos' | 'auditoria' | 'integracion' | 'proceso'
export type RuleApproval = 'borrador' | 'aprobada'
/** Casos de control: lo que el equipo sabe de una regla; mide al programa, no cambia resultados */
export type ControlExpected = 'cumple' | 'viola'
export interface ControlItem {
  rule_id: string
  title: string
  expected: ControlExpected | null
  /** Estado en el último análisis */
  status: RuleStatus | null
  outcome: 'acerto' | 'fallo' | 'sin_resultado' | null
  /** Solidez con que se comprobó: alta | media | baja | ninguna */
  confidence: string | null
}
export interface Concordance {
  items: ControlItem[]
  known: number
  hits: number
  misses: number
  unverified: number
  report_num: number | null
}
/** Respuesta de sí o no a una duda de una regla */
export type DoubtAnswer = 'si' | 'no'

export interface RuleScenario {
  given: string
  when: string
  then: string
}

export interface RulesValidation {
  valid: boolean
  error: string | null
  project: string | null
  rules: RulePreview[]
  /** `rutas` que no existen en el repositorio del proyecto (no impiden guardar) */
  warnings?: string[]
}

export interface RulesFile extends RulesValidation {
  content: string
}

export interface ProjectRules {
  /** Lo que usará el siguiente análisis */
  active: RulesOrigin | null
  repo: (RulesFile & { path: string }) | null
  uploaded: (RulesFile & { updated_at: string }) | null
  /** El repo ya se clonó (si no, todavía no se sabe si trae el archivo) */
  cloned: boolean
  commit: string | null
  /** Documentos de requisitos de la copia del repo (PDF, Word, Markdown) que se pueden importar */
  documents: string[]
  /** Hay IA (Gemini) para importar reglas desde un documento */
  can_import: boolean
  /** Avisos de la última acción (reglas que no se pudieron aprobar y por qué) */
  messages?: string[]
}

/** Archivo de reglas del repo: valid | invalid | missing. unavailable = no se pudo leer sin clonar (acceso, rama, GitHub) */
export type PrecheckStatus = 'valid' | 'invalid' | 'missing' | 'unavailable'

/** Revisión de las reglas al cargar el repo en Nuevo análisis (POST /api/reglas/revisar), antes de clonar. */
export interface RulesPrecheck {
  /** "owner/repo" */
  repo: string
  status: PrecheckStatus
  message: string | null
  file: (RulesFile & { path: string }) | null
  /** El repo ya es un proyecto del equipo */
  project_id: string | null
  uploaded: (RulesFile & { updated_at: string }) | null
  /** Lo que usará el análisis si no se cambia nada */
  active: RulesOrigin | null
  /** Plantilla con el nombre del repo y sus carpetas con código */
  template: string
  /** Validación del contenido enviado (editor del modal) */
  checked: RulesValidation | null
  /** Documentos de requisitos del árbol del repo (los de docs/ primero) */
  documents: string[]
  can_import: boolean
}

/**
 * Importar reglas desde un documento (POST /api/reglas/importar). Una de tres fuentes: el repo en GitHub
 * (url + branch + path), la copia de un proyecto (project_id + path) o un archivo subido (filename + data en base64).
 */
export interface ImportRulesRequest {
  url?: string
  branch?: string
  project_id?: string
  path?: string
  filename?: string
  data?: string
}

/** reglas_negocio.toml que propone la IA desde el documento: no se guarda hasta que el usuario lo usa. */
export interface ImportedRules {
  content: string
  count: number
  /** Ambigüedades del documento */
  doubts: string[]
  /**
   * Reglas que el documento contradice («RN-002 (§2.3) y RN-004 (§5.2): …»). Van marcadas en `content` con
   * `# CONTRADICCIÓN` y el archivo no es válido hasta que se deje una de cada par.
   */
  contradictions: string[]
  source: string
  validation: RulesValidation
  model: string
}

// ─── Mapa del proyecto y arnés de pruebas (docs/PROPUESTA_REGLAS_VERIFICABLES.md §6.2 y §7) ───

/** Lo que el backend encontró en el código leyéndolo con `ast` (sin IA). */
export interface MapSummary {
  framework: string | null
  frameworks: string[]
  endpoints: number
  models: number
  schemas: number
  roles: string[]
  /** Tipos de integración: correo, sms, pagos, http, tareas, push, nube */
  integrations: string[]
  uses_time: boolean
  /** "inventario.main:app", "reservas.app:crear_app" */
  entry: string[]
  warnings: string[]
}

export type SmokeStatus = 'pendiente' | 'corriendo' | 'paso' | 'fallo'
export type HarnessOrigin = 'ia' | 'repo' | 'manual'

export interface SmokeTest {
  /** test_humo_como[cajero], test_humo_crear[crear_producto]… */
  name: string
  outcome: 'passed' | 'failed' | 'error' | 'skipped'
  message: string
}

/** tests/_ia_voy_reglas/conftest.py: los fixtures con los que se escriben las pruebas de cada regla. */
export interface Harness {
  code: string
  origin: HarnessOrigin
  /** conftest.py del repo del que salió (origin = repo) */
  source_path: string | null
  /** Lo que la IA tuvo que suponer */
  assumptions: string[]
  model: string | null
  commit: string | null
  updated_at: string
  fixtures: string[]
  /** Impiden correr la prueba de humo (validación con ast) */
  errors: string[]
  warnings: string[]
  smoke: SmokeStatus
  /** Un solo aviso: la primera falla, con el fixture que la causó */
  smoke_message: string | null
  smoke_tests: SmokeTest[]
  smoke_at: string | null
  approved: boolean
  approved_by: string | null
  approved_at: string | null
}

export interface HarnessView {
  cloned: boolean
  map: MapSummary | null
  harness: Harness | null
  /** conftest.py del repo que ya sirve de arnés (define `api` y `como`) */
  repo_harness: string | null
  can_generate: boolean
  /** Hay sandbox configurado: sin él no se corre la prueba de humo */
  sandbox: boolean
  /** Aprobado con el código actual: ya se pueden generar las pruebas de las reglas */
  ready: boolean
}

// ─── Pruebas de las reglas generadas por IA voy (docs/PROPUESTA_REGLAS_VERIFICABLES.md §6.3, fase 4) ───

export type RuleTestKind = 'prueba' | 'no_implementada' | 'fuera_del_codigo'
export type RuleTestState = 'sin_prueba' | 'borrador' | 'aprobada' | 'desactualizada'
export type RunVerdict = 'cumple' | 'no_cumple' | 'prueba_rota' | 'sin_verificar'

export interface RuleTestRun {
  verdict: RunVerdict
  detail: string
  tests: { name: string; outcome: TestOutcome; message: string }[]
}

// ─── Fase 5: prueba de fuerza, evidencia de apoyo y matriz de permisos ───

/** fuerte = notó todos los cambios a las líneas de la regla; débil = ninguno (la prueba no verifica la regla) */
export type StrengthStatus = 'fuerte' | 'parcial' | 'debil' | 'no_aplica'

export interface StrengthResult {
  status: StrengthStatus
  detail: string
  killed: number
  total: number
  /** Cambios que la prueba no notó */
  survivors: { file: string; line: number; description: string }[]
  /** Qué se mutó: las líneas de la evidencia o las de los endpoints que llama la prueba */
  source: string
}

/** Dónde parece estar implementada la regla, según la IA. No cambia su estado ni el score. */
export interface SupportEvidence {
  verdict: 'implementada' | 'parcial' | 'no_encontrada'
  summary: string
  places: { file: string; start: number; end: number; why: string }[]
  model: string
  /** De dónde salieron los fragmentos: indice (RAG) y/o palabras */
  search: string[]
  created_at: string
  /** De otra versión de la regla o de otro commit */
  stale: boolean
}

/** Contraste entre la prueba corrida y la IA leyendo el código sin ver la prueba (no cuenta en el score) */
export interface Crosscheck {
  status: 'coincide' | 'discrepa' | 'sin_revisar'
  note: string
}

export type MatrixCell = 'permitido' | 'prohibido'

export interface MatrixAction {
  /** "PATCH /servicios/{servicio_id}" */
  id: string
  method: string
  path: string
  function: string
  /** Roles que el código deja pasar hoy (sugerencia, no oráculo) */
  suggested: string[]
  cells: Partial<Record<string, MatrixCell>>
}

export interface PermissionMatrix {
  rule_id: string
  roles: string[]
  actions: MatrixAction[]
  saved: boolean
}

export interface GeneratedTest {
  kind: RuleTestKind
  /** datos | flujo | calculo | permisos | auditoria | integracion | proceso */
  tipo: string
  file: string
  code: string
  /** matriz = salió de la matriz de permisos, sin IA */
  origin: 'ia' | 'manual' | 'matriz'
  assumptions: string[]
  endpoints: string[]
  /** Por qué no está implementada o está fuera del código */
  reason: string | null
  model: string | null
  errors: string[]
  warnings: string[]
  tests: string[]
  /** La regla cambió desde que se generó la prueba */
  outdated: boolean
  /** Rutas que la prueba usa y que el código ya no tiene: hay que escribirla de nuevo */
  gone_endpoints?: string[]
  run_status: 'pendiente' | 'corriendo' | 'hecho'
  run: RuleTestRun | null
  approved: boolean
  approved_by: string | null
  approved_at: string | null
  /** Por qué no se puede aprobar todavía (null = se puede) */
  blocked: string | null
  updated_at: string
  /** Prueba de fuerza del código actual de la prueba */
  strength_status: 'pendiente' | 'corriendo' | 'hecho'
  strength: StrengthResult | null
  /** Por qué no se puede hacer la prueba de fuerza (null = se puede: la prueba pasa) */
  strength_blocked: string | null
  has_matrix: boolean
}

export interface RuleTestRow {
  id: string
  title: string
  description: string
  severity: Severity
  criterion: string | null
  /** Pruebas del repo que ya la verifican: tienen prioridad sobre la generada */
  repo_tests: number
  state: RuleTestState
  test: GeneratedTest | null
  /** La regla habla de permisos o roles: se le ofrece la matriz */
  permissions: boolean
  evidence: SupportEvidence | null
  crosscheck: Crosscheck
}

export interface RuleTestsView {
  cloned: boolean
  source: string | null
  error: string | null
  harness_ready: boolean
  can_generate: boolean
  /** Hay IA para pedir la evidencia de apoyo */
  can_explain: boolean
  sandbox: boolean
  rules: RuleTestRow[]
  /** Generando, corriendo o haciendo la prueba de fuerza en segundo plano */
  busy: { kind: 'generando' | 'corriendo' | 'fuerza'; total: number; done: number; current: string | null } | null
  /** Avisos del último trabajo (reglas que la IA no pudo generar, las que no se aprobaron y por qué) */
  messages: string[]
}

/** «Preparar todo» corre en el servidor: sigue aunque se cierre la pestaña (docs/PLAN_REGLAS_AUTOMATICO.md, paso 1) */
export type PrepareStepId = 'reglas' | 'arnes' | 'humo' | 'pruebas' | 'correr' | 'fuerza' | 'revision'
export type PrepareStatus = 'pendiente' | 'haciendo' | 'hecho' | 'fallo'
export interface PrepareStep {
  id: PrepareStepId
  label: string
  status: PrepareStatus
  /** Lo que pasó, en una frase (qué se hizo o por qué se detuvo y cómo resolverlo) */
  note: string | null
}
export interface PrepareView {
  running: boolean
  steps: PrepareStep[]
  summary: string | null
  started_at: string | null
  finished_at: string | null
}
