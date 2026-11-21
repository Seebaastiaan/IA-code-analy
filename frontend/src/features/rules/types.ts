import type { Severity } from '@/shared/types/common'

/** Reglas de negocio del proyecto (backend/app/analyses/reglas.py, docs/adr/ADR-003-reglas-de-negocio.md). */

export type RuleStatus = 'cumple' | 'no_cumple' | 'sin_verificar'
/** Cómo se verificó la regla */
export type RuleLevel = 'pruebas' | 'patron' | 'pruebas_y_patron' | 'ninguno'
/** passed…not_run: corrió en el sandbox (plugin ia_voy_reglas); sin_ejecutar: se encontró leyendo el código */
export type TestOutcome = 'passed' | 'failed' | 'error' | 'skipped' | 'not_run' | 'sin_ejecutar'
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
  summary: { total: number; cumple: number; no_cumple: number; sin_verificar: number }
  rules: BusinessRuleResult[]
}

export interface RulePreview {
  id: string
  title: string
  severity: Severity
  /** Tiene `prohibido` u `obligatorio` */
  pattern: boolean
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
