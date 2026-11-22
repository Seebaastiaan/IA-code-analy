export type Category = 'seg' | 'test' | 'prac'
export type Severity = 'alta' | 'media' | 'baja'
export type RepoStatus = 'listo' | 'analizando' | 'error'
export type ScoreTone = 'good' | 'warn' | 'bad'

/** Pesos del score. `neg` (reglas de negocio) pesa 0 por defecto: solo mueve el global si el proyecto le da un peso. */
export type Weights = Record<Category, number> & { neg?: number }

/** Puntuaciones 0–100: global (ponderada) y por categoría */
export interface Scores extends Record<Category, number> {
  /** Reglas de negocio; null/ausente = el análisis no tiene reglas medibles */
  neg?: number | null
  global: number
}

export interface Thresholds {
  score: number
  cov: number
}

export const CATEGORIES: Category[] = ['seg', 'test', 'prac']
export const SEVERITIES: Severity[] = ['alta', 'media', 'baja']
