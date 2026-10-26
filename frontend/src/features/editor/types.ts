export interface FileResponse {
  path: string
  language: string
  content: string
}

export interface SaveFileRequest {
  repo_id: string
  path: string
  content: string
}

/** El backend guarda (con respaldo), re-analiza el archivo y devuelve el efecto en el score. */
export interface SaveFileResponse {
  resolved_ids: number[]
  score_before: number
  score_after: number
}
