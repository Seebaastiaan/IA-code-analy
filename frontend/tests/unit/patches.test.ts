import { describe, expect, it } from 'vitest'
import { applyPatches } from '@/features/editor/utils/patches'
import type { Patch } from '@/features/findings/types'

const SRC = ['import os', 'import sys', '', 'def f(x=[]):', '    return x'].join('\n')
const p = (line: number, original: string, text: string | null): Patch => ({ file: 'a.py', line, original, text })

describe('applyPatches', () => {
  it('reemplaza una línea', () => {
    const r = applyPatches(SRC, [p(4, 'def f(x=[]):', 'def f(x=None):')])
    expect(r.content.split('\n')[3]).toBe('def f(x=None):')
    expect(r.missed).toBe(0)
  })

  it('borra una línea cuando text es null', () => {
    const r = applyPatches(SRC, [p(1, 'import os', null)])
    expect(r.content.split('\n')[0]).toBe('import sys')
  })

  it('aplica varios parches sin que los borrados desplacen a los siguientes', () => {
    const r = applyPatches(SRC, [p(1, 'import os', null), p(4, 'def f(x=[]):', 'def f(x=None):')])
    expect(r.content).toBe(['import sys', '', 'def f(x=None):', '    return x'].join('\n'))
  })

  it('expande un reemplazo de varias líneas', () => {
    const r = applyPatches(SRC, [p(5, '    return x', '    x = x or []\n    return x')])
    expect(r.content.split('\n')).toHaveLength(6)
  })

  it('encuentra la línea aunque el borrador la haya movido', () => {
    const edited = `# cabecera nueva\n${SRC}`
    const r = applyPatches(edited, [p(4, 'def f(x=[]):', 'def f(x=None):')])
    expect(r.content.split('\n')[4]).toBe('def f(x=None):')
  })

  it('cuenta los parches cuya línea ya no existe', () => {
    const r = applyPatches(SRC, [p(2, 'import json', null)])
    expect(r.missed).toBe(1)
    expect(r.content).toBe(SRC)
  })
})
