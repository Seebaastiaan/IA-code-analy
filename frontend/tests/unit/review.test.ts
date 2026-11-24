import { describe, expect, it } from 'vitest'
import type { GeneratedTest, RuleTestRow, RuleTestsView, StrengthStatus } from '@/features/rules/types'
import { brokenCount, reviewItems } from '@/features/rules/utils/review'

const test = (verdict: 'cumple' | 'no_cumple' | 'prueba_rota', strength: StrengthStatus | null, extra: Partial<GeneratedTest> = {}): GeneratedTest => ({
  kind: 'prueba', tipo: 'datos', file: 'f.py', code: '', origin: 'ia', assumptions: [], endpoints: [], reason: null, model: null, errors: [], warnings: [],
  tests: [], outdated: false, run_status: 'hecho', approved: false, approved_by: null, approved_at: null, blocked: null, updated_at: '',
  strength_status: 'hecho', strength_blocked: null, has_matrix: false,
  run: { verdict, detail: '', tests: verdict === 'no_cumple' ? [{ name: 't', outcome: 'failed', message: 'assert 200 == 409' }] : [] },
  strength: strength ? { status: strength, detail: '', killed: strength === 'fuerte' ? 3 : 1, total: 3, survivors: [], source: '' } : null,
  ...extra,
})

const row = (id: string, t: GeneratedTest | null, cross: 'coincide' | 'discrepa' | 'sin_revisar'): RuleTestRow => ({
  id, title: id, description: '', severity: 'media', criterion: null, repo_tests: 0, state: 'pendiente' as RuleTestRow['state'], test: t,
  permissions: false, evidence: null, crosscheck: { status: cross, note: '' },
})

const view = (rules: RuleTestRow[]) => ({ rules }) as RuleTestsView

describe('reviewItems', () => {
  it('lista solo las pruebas sin aprobar que dieron un resultado, con el motivo en palabras', () => {
    const items = reviewItems(
      view([
        row('RN-001', test('cumple', 'parcial'), 'coincide'),
        row('RN-002', test('no_cumple', null), 'discrepa'),
        row('RN-003', test('cumple', 'fuerte', { approved: true }), 'coincide'),
        row('RN-004', test('prueba_rota', null), 'sin_revisar'),
        row('RN-005', null, 'sin_revisar'),
        row('RN-006', test('cumple', 'fuerte'), 'sin_revisar'),
      ]),
    )
    expect(items.map((i) => i.row.id)).toEqual(['RN-001', 'RN-002', 'RN-006'])
    const [floja, falla, sinLeer] = items
    // Floja: no conviene aprobarla, «Volver a preparar» la reescribe
    expect(floja.why).toEqual(['Siguió pasando con 2 de 3 cambios al código: puede que no compruebe la regla'])
    expect(floja.recommended).toBe(false)
    expect(floja.advice).toContain('Volver a preparar')
    // Falla y la lectura del código dice lo contrario: se muestra el fallo para decidir
    expect(falla.passes).toBe(false)
    expect(falla.failure).toBe('assert 200 == 409')
    expect(falla.why).toEqual(['La IA leyó el código y cree que la regla sí está'])
    expect(falla.recommended).toBe(false)
    // Fuerte, pero sin segunda opinión: se puede aprobar
    expect(sinLeer.why).toEqual(['Falta la segunda opinión (la IA no respondió)'])
    expect(sinLeer.recommended).toBe(true)
  })

  it('cuenta aparte las pruebas que no pudieron preparar su caso', () => {
    expect(brokenCount(view([row('RN-004', test('prueba_rota', null), 'sin_revisar'), row('RN-001', test('cumple', 'fuerte'), 'coincide')]))).toBe(1)
    expect(reviewItems(undefined)).toEqual([])
  })
})
