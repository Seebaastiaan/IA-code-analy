import type { Category, Severity } from '@/shared/types/common'
import type { SnippetLine } from '@/shared/ui'

export type Tool = 'Bandit' | 'pip-audit' | 'pytest' | 'coverage' | 'Ruff' | 'Radon'

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
  /** Hay corrección automática */
  fix: boolean
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
}
