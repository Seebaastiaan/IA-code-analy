import { describe, expect, it } from 'vitest'
import type { BusinessRuleResult, RuleStatus } from '@/features/rules/types'
import { filterRules, testFunction, testName } from '@/features/rules/utils/rules'
import { templateFor, validate, validateFor } from '@/mocks/rules'

const rule = (id: string, status: RuleStatus): BusinessRuleResult => ({
  id, title: id, description: '', severity: 'media', paths: [], forbidden: null, required: null, story: null, owner: null, criterion: null,
  status, level: 'ninguno', detail: '', evidence: [], evidence_total: 0, tests: [],
})

describe('filterRules', () => {
  const rules = [rule('RN-001', 'cumple'), rule('RN-002', 'no_cumple'), rule('RN-003', 'sin_verificar'), rule('RN-004', 'no_cumple')]

  it('pone primero las que no cumplen y conserva el orden del archivo', () => {
    expect(filterRules(rules, 'todas').map((r) => r.id)).toEqual(['RN-002', 'RN-004', 'RN-003', 'RN-001'])
  })

  it('filtra por estado', () => {
    expect(filterRules(rules, 'cumple').map((r) => r.id)).toEqual(['RN-001'])
    expect(filterRules([], 'no_cumple')).toEqual([])
  })
})

describe('nombres de prueba', () => {
  it('sugiere el nombre alternativo al marcador', () => {
    expect(testName('RN-002')).toBe('test_rn002_…')
  })

  it('saca la función del nodeid de pytest', () => {
    expect(testFunction('tests/test_pedidos.py::TestPedido::test_cancelado')).toBe('TestPedido::test_cancelado')
    expect(testFunction('raro')).toBe('raro')
  })
})

describe('validación simulada de reglas_negocio.toml', () => {
  const base = '[proyecto]\nnombre = "Tienda"\n\n[[regla]]\nid = "RN-001"\ntitulo = "T"\ndescripcion = "D"\nseveridad = "alta"\n'

  it('acepta un archivo válido', () => {
    expect(validate(base)).toEqual({ valid: true, error: null, project: 'Tienda', rules: [{ id: 'RN-001', title: 'T', severity: 'alta', pattern: false }] })
  })

  it('indica la línea del error, como el backend', () => {
    expect(validate(base.replace('RN-001', 'RN-1')).error).toBe('línea 4: `RN-1` no cumple el formato `RN-###` (p. ej. RN-001)')
    expect(validate(base.replace('[proyecto]', '')).valid).toBe(false)
  })
})

describe('reglas de cada proyecto (simuladas)', () => {
  it('la plantilla lleva el nombre del proyecto, no uno general', () => {
    const r1 = templateFor('r1')
    const r2 = templateFor('r2')
    expect(r1).not.toContain('Mi proyecto')
    expect(validate(r1).project).not.toBe(validate(r2).project)
  })

  it('avisa las rutas que no existen en el repositorio del proyecto', () => {
    const toml = '[proyecto]\nnombre = "X"\n\n[[regla]]\nid = "RN-001"\ntitulo = "T"\ndescripcion = "D"\nseveridad = "alta"\nrutas = ["no_existe/"]\n'
    const result = validateFor('r1', toml)
    expect(result.valid).toBe(true)
    expect(result.warnings).toEqual([expect.stringContaining('`no_existe/` no existe en')])
  })
})
