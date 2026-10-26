import type { Patch } from '@/features/findings/types'

/** Busca la línea original cerca de su posición esperada (el borrador puede haberla desplazado). */
function locate(lines: string[], original: string, hint: number): number {
  if (lines[hint] === original) return hint
  for (let d = 1; d < lines.length; d++) {
    if (lines[hint - d] === original) return hint - d
    if (lines[hint + d] === original) return hint + d
  }
  return -1
}

/**
 * Aplica parches de una corrección sobre el texto actual. Se procesan de abajo hacia arriba para que
 * las líneas pendientes no cambien de posición. Devuelve también cuántos parches no encontraron su línea.
 */
export function applyPatches(content: string, patches: Patch[]): { content: string; missed: number } {
  const lines = content.split('\n')
  let missed = 0
  for (const p of [...patches].sort((a, b) => b.line - a.line)) {
    const i = locate(lines, p.original, p.line - 1)
    if (i < 0) {
      missed++
      continue
    }
    if (p.text === null) lines.splice(i, 1)
    else lines.splice(i, 1, ...p.text.split('\n'))
  }
  return { content: lines.join('\n'), missed }
}
