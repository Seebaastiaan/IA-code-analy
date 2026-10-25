import { weightSum } from '@/shared/utils/score'
import type { ProjectConfig } from '../types'

const list = (xs: string[]) => `[${xs.map((x) => JSON.stringify(x)).join(', ')}]`

/** Vista previa de .ia_voy.toml (el backend es quien escribe el archivo real). */
export function toToml(c: ProjectConfig): string {
  const s = weightSum(c.weights) || 1
  return `# .ia_voy.toml
[pesos]
seguridad = ${(c.weights.seg / s).toFixed(2)}
pruebas   = ${(c.weights.test / s).toFixed(2)}
practicas = ${(c.weights.prac / s).toFixed(2)}

[umbrales]
score_minimo     = ${c.thresholds.score}
cobertura_minima = ${c.thresholds.cov}

[reglas]
ignorar = ${list(c.ignored)}

[rutas]
excluir = ${list(c.excluded)}`
}
