import type { Category, Severity } from '@/shared/types/common'
import type { SnippetLine } from '@/shared/ui'

export type Tool = 'Bandit' | 'pip-audit' | 'pytest' | 'coverage' | 'Ruff' | 'Radon'

export type FixKind = 'auto' | 'ia'

/** La corrección la propone la IA (no la herramienta). */
export const isAiFix = (f: Pick<Finding, 'fix' | 'fix_kind'>) => f.fix && f.fix_kind === 'ia'

export interface Finding {
  id: number
  sev: Severity
  cat: Category
  tool: Tool
  /** "B105", "F401", "COV", "FAIL", "requests 2.25.1"… */
  rule: string
  file: string
  line: number
  msg: string
  /** Por qué importa */
  why: string
  /** Cómo corregirlo */
  rec: string
  /** Hay corrección (de la herramienta o de la IA) */
  fix: boolean
  /** auto: Ruff / versión de pip-audit · ia: la propone el LLM; en ambos casos se revisa el diff antes de guardar */
  fix_kind?: FixKind | null
  status: 'open' | 'resolved'
  /** ±2 líneas alrededor del hallazgo (se omite en enlaces públicos sin código) */
  snippet?: SnippetLine[]
}

/** Cambio de una línea propuesto por una corrección automática. */
export interface Patch {
  file: string
  line: number
  /** Texto original de la línea: permite ubicarla aunque el borrador haya cambiado */
  original: string
  /** Nuevo texto (puede tener saltos de línea); null = borrar la línea */
  text: string | null
}

export interface FixRequest {
  repo_id: string
  finding_ids: number[]
}

export interface FixResponse {
  patches: Patch[]
  /** Qué cambió la IA y por qué, por archivo */
  notes?: string[]
}
