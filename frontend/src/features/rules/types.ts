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
}
