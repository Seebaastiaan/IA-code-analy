export interface Source {
  file: string
  line: number
}

export interface HistoryTurn {
  role: 'user' | 'model'
  content: string
}

export interface ChatRequest {
  repo_id: string
  message: string
  /** Mensajes anteriores de la conversación, para preguntas de seguimiento */
  history?: HistoryTurn[]
}

export interface ChatResponse {
  /** Markdown mínimo: `código`, **negrita**, saltos de línea */
  content: string
  sources: Source[]
  /** Acción sugerida (p. ej. aplicar el fix de un hallazgo) */
  action?: { finding_id: number; label: string }
  /** Modelo que respondió (el principal, o un respaldo si no estaba disponible) */
  model: string
}

export interface ChatMessage {
  id: number
  role: 'me' | 'ai'
  content: string
  sources?: Source[]
  action?: ChatResponse['action']
  model?: string
  error?: boolean
  /** La respuesta aún está llegando por streaming */
  streaming?: boolean
}

/** ready: listo · building: indexando por primera vez · not_configured: falta la clave · not_cloned: sin código */
export type IndexStatus = 'ready' | 'building' | 'not_configured' | 'not_cloned' | 'error'

export interface IndexInfo {
  py_files: number
  chunks: number
  readme: boolean
  report_num: number | null
  model: string
  fallback: string
  status?: IndexStatus
  /** Motivo cuando status === 'error' (la indexación falló; el servidor reintenta en un minuto) */
  error?: string | null
}
