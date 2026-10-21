import type { Weights } from '@/shared/types/common'

export const DEFAULT_WEIGHTS: Weights = { seg: 50, test: 30, prac: 20 }

export const weightSum = (w: Weights) => w.seg + w.test + w.prac

/** Promedio ponderado; normaliza si los pesos no suman 100. Solo para previsualizar: el oficial lo calcula el backend. */
export function calcScore(w: Weights, s: Weights): number {
  const sum = weightSum(w) || 1
  return (w.seg * s.seg + w.test * s.test + w.prac * s.prac) / sum
}

/** Formatea con un decimal. */
export const f1 = (v: number) => (Math.round(v * 10) / 10).toFixed(1)
