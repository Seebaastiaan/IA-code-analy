import type { Category, Severity } from '@/shared/types/common'

export interface DiagnosticoRequest {
  url: string
  branch: string
  /** Archivo .py del repo; vacío = el primero que no sea de pruebas */
  file?: string | null
}

export interface Hallazgo {
  categoria: Category
  severidad: Severity
  linea: number
  regla: string
  mensaje: string
  recomendacion: string
}

/** POST /api/diagnostico: la IA diagnostica UN archivo del repo clonado (prototipo del Sprint 3). */
export interface DiagnosticoResponse {
  repo: string
  branch: string
  commit: string
  file: string
  files: string[]
  model: string
  diagnostico: {
    resumen: string
    score: number
    hallazgos: Hallazgo[]
  }
}
