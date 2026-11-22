import type { Weights } from '@/shared/types/common'

export const DEFAULT_WEIGHTS: Weights = { seg: 50, test: 30, prac: 20, neg: 0 }

export const weightSum = (w: Weights) => w.seg + w.test + w.prac + (w.neg ?? 0)

/** `neg` entra al score solo con peso y con una nota (el análisis tuvo reglas medibles). */
export const usesNeg = (w: Weights, s?: { neg?: number | null }) => (w.neg ?? 0) > 0 && s?.neg != null

/** Promedio ponderado; normaliza si los pesos no suman 100. Solo para previsualizar: el oficial lo calcula el backend. */
export function calcScore(w: Weights, s: Weights & { neg?: number | null }): number {
  const neg = usesNeg(w, s)
  const sum = (w.seg + w.test + w.prac + (neg ? (w.neg ?? 0) : 0)) || 1
  return (w.seg * s.seg + w.test * s.test + w.prac * s.prac + (neg ? (w.neg ?? 0) * (s.neg ?? 0) : 0)) / sum
}

/** Formatea con un decimal. */
export const f1 = (v: number) => (Math.round(v * 10) / 10).toFixed(1)
