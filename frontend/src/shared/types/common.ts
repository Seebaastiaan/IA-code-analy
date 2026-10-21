export type Category = 'seg' | 'test' | 'prac'
export type Severity = 'alta' | 'media' | 'baja'
export type RepoStatus = 'listo' | 'analizando' | 'error'
export type ScoreTone = 'good' | 'warn' | 'bad'

export type Weights = Record<Category, number>

/** Puntuaciones 0–100: global (ponderada) y por categoría */
export interface Scores extends Weights {
  global: number
}

export interface Thresholds {
  score: number
  cov: number
}

export const CATEGORIES: Category[] = ['seg', 'test', 'prac']
export const SEVERITIES: Severity[] = ['alta', 'media', 'baja']
