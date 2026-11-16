import { describe, expect, it } from 'vitest'
import type { BusinessRuleResult, RulesPrecheck, RuleStatus, RulesValidation } from '@/features/rules/types'
import { filterRules, githubRepo, precheckView, testFunction, testName } from '@/features/rules/utils/rules'
import { fromAnalyze, precheck, templateFor, validate, validateFor } from '@/mocks/rules'

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

describe('revisión de reglas en Nuevo análisis', () => {
  const ok = (rules = 2, project = 'Tienda'): RulesValidation => ({
    valid: true, error: null, project, rules: Array.from({ length: rules }, (_, i) => ({ id: `RN-00${i + 1}`, title: 'T', severity: 'alta', pattern: false })), warnings: [],
  })
  const bad: RulesValidation = { valid: false, error: 'línea 9: `R1` no cumple el formato `RN-###` (p. ej. RN-001)', project: null, rules: [] }
  const check = (over: Partial<RulesPrecheck>): RulesPrecheck => ({
    repo: 'equipo/tienda', status: 'missing', message: null, file: null, project_id: null, uploaded: null, active: null, template: '', checked: null, ...over,
  })
  const file = (v: RulesValidation) => ({ ...v, content: 'x', path: 'reglas_negocio.toml' })

  it('saca owner/repo solo de URLs de GitHub, como el backend', () => {
    expect(githubRepo(' https://github.com/equipo/tienda.git ')).toBe('equipo/tienda')
    expect(githubRepo('https://www.github.com/equipo/tienda/')).toBe('equipo/tienda')
    expect(githubRepo('https://gitlab.com/equipo/tienda')).toBeNull()
    expect(githubRepo('https://github.com/equipo')).toBeNull()
  })

  it('archivo válido del repo: lo usa y gana a las escritas en el formulario', () => {
    const p = check({ status: 'valid', file: file(ok(4)), active: 'repo' })
    expect(precheckView(p, null)).toMatchObject({ tone: 'ok', uses: 'repo', title: '4 regla(s) · Tienda de negocio' })
    expect(precheckView(p, ok()).detail).toContain('el archivo válido del repositorio gana')
  })

  it('archivo con errores: muestra el error y, si hay, usa las corregidas', () => {
    const p = check({ status: 'invalid', file: file(bad), active: 'repo' })
    expect(precheckView(p, null)).toEqual({ tone: 'error', uses: null, title: 'reglas_negocio.toml no es válido', detail: bad.error })
    expect(precheckView({ ...p, uploaded: { ...ok(3), content: 'y', updated_at: '' }, active: 'app' }, null)).toMatchObject({ tone: 'warn', uses: 'app' })
    const form = precheckView(p, ok(3))
    expect(form).toMatchObject({ tone: 'ok', uses: 'form', title: '3 regla(s) · Tienda escritas aquí' })
    expect(form.detail).toContain('usará estas reglas corregidas')
  })

  it('sin archivo o sin acceso: nunca bloquea', () => {
    expect(precheckView(check({}), null)).toMatchObject({ tone: 'neutral', uses: null, title: 'Este repo no declara reglas de negocio' })
    expect(precheckView(check({ uploaded: { ...ok(), content: 'y', updated_at: '' } }), null).uses).toBe('app')
    expect(precheckView(check({ status: 'unavailable', message: 'Sin acceso' }), null)).toMatchObject({ tone: 'neutral', detail: 'Sin acceso' })
  })

  it('simulada: lee el archivo del repo, valida el contenido y guarda las reglas del análisis', () => {
    expect(precheck('https://github.com/equipo/api-pagos', 'main')).toMatchObject({ status: 'valid', project_id: 'r1', active: 'repo' })
    const scraper = precheck('https://github.com/ana-lopez/scraper-precios', 'main')!
    expect(scraper).toMatchObject({ status: 'invalid', project_id: null })
    expect(scraper.file?.error).toContain('`R1` no cumple el formato')
    expect(precheck('https://github.com/ana-lopez/scraper-precios', 'main', scraper.file!.content.replace('"R1"', '"RN-001"'))!.checked?.valid).toBe(true)
    expect(precheck('https://github.com/nadie/nada', 'main')!.status).toBe('unavailable')
    expect(precheck('https://gitlab.com/a/b', 'main')).toBeNull()
    expect(fromAnalyze('https://github.com/ana-lopez/scraper-precios', scraper.file!.content)).toContain('RN-###')
  })
})
