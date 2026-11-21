import { describe, expect, it } from 'vitest'
import type { BusinessRuleResult, RulesPrecheck, RuleStatus, RulesValidation } from '@/features/rules/types'
import { baseName, fileToBase64, filterRules, githubRepo, isDocument, precheckView, testFunction, testName } from '@/features/rules/utils/rules'
import { fromAnalyze, importDocument, precheck, templateFor, validate, validateFor } from '@/mocks/rules'

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
    expect(validate(base)).toEqual({ valid: true, error: null, project: 'Tienda', rules: [{ id: 'RN-001', title: 'T', severity: 'alta', pattern: false }], warnings: [] })
  })

  it('indica la línea del error, como el backend', () => {
    expect(validate(base.replace('RN-001', 'RN-1')).error).toBe('línea 4: `RN-1` no cumple el formato `RN-###` (p. ej. RN-001)')
    expect(validate(base.replace('[proyecto]', '')).valid).toBe(false)
    expect(validate(base.replace('nombre = "Tienda"', 'nombre = "Tienda"\nautor = "X"')).error).toBe('[proyecto]: campo desconocido `autor` (campos válidos: nombre, version)')
    expect(validate(`${base}rutas = "app/"\n`).error).toContain('`rutas` debe ser una lista')
    expect(validate(`${base}prohibido = 'round('\n`).error).toBe('línea 4 · RN-001: `prohibido` no es una expresión regular válida')
  })

  const dos = (a: string, b: string) =>
    `[proyecto]\nnombre = "P"\n\n[[regla]]\nid = "RN-001"\ntitulo = "T1"\ndescripcion = "D1"\nseveridad = "alta"\n${a}\n\n[[regla]]\nid = "RN-002"\ntitulo = "T2"\ndescripcion = "D2"\nseveridad = "alta"\n${b}\n`

  it('avisa reglas que se contradicen, como el backend', () => {
    const r = validate(dos("prohibido = 'print'\nrutas = [\"app/\"]", "obligatorio = 'print'\nrutas = [\"app/pagos/cobro.py\"]"))
    expect(r.valid).toBe(true)
    expect(r.warnings).toEqual(['RN-001 y RN-002 se contradicen: RN-002 exige `print` y RN-001 prohíbe `print` en las mismas rutas; no pueden cumplirse las dos'])
    // Rutas distintas, o un obligatorio que es regex de verdad: no se contradicen
    expect(validate(dos("prohibido = 'print'\nrutas = [\"app/a/\"]", "obligatorio = 'print'\nrutas = [\"app/b/\"]")).warnings).toEqual([])
    expect(validate(dos("prohibido = 'float'", "obligatorio = 'float|Decimal'")).warnings).toEqual([])
  })

  it('avisa reglas duplicadas', () => {
    const r = validate(dos("prohibido = 'x'\nrutas = [\"a/\", \"b/\"]", "prohibido = 'x'\nrutas = [\"b/\", \"./a/\"]").replace('"T2"', '" t1. "'))
    expect(r.warnings).toEqual(['RN-002 parece duplicada de RN-001: tiene el mismo patrón y rutas y el mismo título'])
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
    repo: 'equipo/tienda', status: 'missing', message: null, file: null, project_id: null, uploaded: null, active: null, template: '', checked: null,
    documents: [], can_import: false, ...over,
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

  it('sin archivo pero con documento de requisitos: ofrece sacar las reglas con IA (solo si hay IA)', () => {
    const docs = check({ documents: ['docs/Requerimientos.pdf'], can_import: true })
    expect(precheckView(docs, null)).toMatchObject({ tone: 'neutral', uses: null, title: 'Este repo no declara reglas de negocio' })
    expect(precheckView(docs, null).detail).toContain('Encontré docs/Requerimientos.pdf en el repositorio')
    expect(precheckView({ ...docs, documents: ['a.md', 'b.pdf'] }, null).detail).toContain('2 documentos de requisitos')
    expect(precheckView({ ...docs, can_import: false }, null).detail).toContain('Descarga la plantilla')
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

  it('simulada: los repos CRUD de prueba traen sus reglas reales', () => {
    const biblioteca = precheck('https://github.com/urielbatizzzzzzzz/crud-biblioteca', 'main')!
    expect(biblioteca).toMatchObject({ status: 'valid', active: 'repo' })
    expect(biblioteca.file).toMatchObject({ project: 'Biblioteca escolar', warnings: [] })
    expect(biblioteca.file!.rules.map((r) => r.id)).toEqual(['RN-001', 'RN-002', 'RN-003', 'RN-004', 'RN-005'])
    const cafeteria = precheck('https://github.com/urielbatizzzzzzzz/crud-cafeteria', 'main')!
    expect(cafeteria.file).toMatchObject({ valid: true, project: 'Cafetería escolar', warnings: [] })
    expect(cafeteria.file!.rules.filter((r) => r.pattern).map((r) => r.id)).toEqual(['RN-001', 'RN-003'])

    // Papelería: sus 8 errores de formato salen en orden, como en el backend (ver su README)
    const papeleria = precheck('https://github.com/urielbatizzzzzzzz/crud-papeleria', 'main')!
    expect(papeleria.status).toBe('invalid')
    let text = papeleria.file!.content
    const fixes: [string, string][] = [
      ['autor   = "Equipo 11"', ''],
      ['"R1"', '"RN-001"'],
      ['"critica"', '"alta"'],
      ['titulo      = "Ningún artículo cuesta $0 o menos"', 'titulo      = "Ningún artículo cuesta $0 o menos"\ndescripcion = "x"'],
      ['rutas       = "papeleria/ventas.py"', 'rutas       = ["papeleria/ventas.py"]'],
      ['prioridad   = 1', ''],
      ["'round('", "'round\\('"],
      ['id          = "RN-006"                     # ERROR 8', 'id          = "RN-007"'],
    ]
    const errors = fixes.map(([from, to]) => {
      const error = validate(text).error
      text = text.replace(from, to)
      return error
    })
    expect(errors.map((e) => e?.replace(/ \(.*$/, ''))).toEqual([
      '[proyecto]: campo desconocido `autor`',
      'línea 11: `R1` no cumple el formato `RN-###`',
      'línea 20 · RN-002: `severidad` debe ser alta, media o baja',
      'línea 27 · RN-003: falta `descripcion`',
      'línea 34 · RN-004: `rutas` debe ser una lista, p. ej. ["app/pagos/"]',
      'línea 42: campo desconocido `prioridad`',
      'línea 50 · RN-006: `prohibido` no es una expresión regular válida',
      'línea 58: RN-006 está repetida',
    ])
    expect(validate(text)).toMatchObject({ valid: true, project: 'Papelería escolar', warnings: [] })
  })
})

describe('importar reglas desde un documento', () => {
  it('reconoce los documentos que lee la IA', () => {
    expect(['Requerimientos.PDF', 'reglas.docx', 'srs.md', 'notas.txt'].every(isDocument)).toBe(true)
    expect(isDocument('reglas_negocio.toml')).toBe(false)
    expect(isDocument('foto.png')).toBe(false)
    expect(baseName('docs/sub/Requerimientos.pdf')).toBe('Requerimientos.pdf')
  })

  it('convierte el archivo a base64 (también archivos grandes)', async () => {
    expect(await fileToBase64(new Blob(['%PDF-1.4 ñ']))).toBe(btoa(unescape(encodeURIComponent('%PDF-1.4 ñ'))))
    const big = new Uint8Array(100_000).fill(65)
    expect(await fileToBase64(new Blob([big]))).toBe(btoa('A'.repeat(100_000)))
  })

  it('simulada: el repo con documento lo muestra en la revisión y la IA devuelve un TOML válido', () => {
    expect(precheck('https://github.com/equipo/bot-soporte', 'main')).toMatchObject({ documents: ['docs/Requerimientos.pdf'], can_import: true })
    expect(precheck('https://github.com/equipo/api-pagos', 'main')!.documents).toEqual([])
    const r = importDocument({ url: 'https://github.com/equipo/bot-soporte', branch: 'main', path: 'docs/Requerimientos.pdf' })
    if (typeof r === 'string') throw new Error(r)
    expect(r.validation).toMatchObject({ valid: true, project: 'equipo/bot-soporte' })
    expect(r.validation.rules.map((x) => x.id)).toEqual(['RN-001', 'RN-002', 'RN-003'])
    expect(r.content).toContain('# Fuente: pág. 3 · §2.1\n[[regla]]')
    expect(r.doubts.length).toBeGreaterThan(0)
    expect(importDocument({ filename: 'virus.exe', data: '' })).toContain('Usa un PDF')
    expect(r.contradictions).toEqual([])
  })

  it('simulada: un documento que se contradice marca el par y no es válido hasta dejar una regla', () => {
    const r = importDocument({ filename: 'Requisitos.pdf', data: '' })
    if (typeof r === 'string') throw new Error(r)
    expect(r.count).toBe(4)
    expect(r.contradictions).toEqual([expect.stringMatching(/^RN-002 \(pág\. 4 · §2\.3\) y RN-004 \(pág\. 7 · §5\.2\): /)])
    expect(r.content.match(/# CONTRADICCIÓN RN-002 RN-004: /g)).toHaveLength(2)
    expect(r.validation.valid).toBe(false)
    expect(r.validation.error).toMatch(/RN-002 y RN-004 se contradicen según el documento/)
    // Se deja la de 1 hora: ya es válido
    const sinRN004 = r.content.split('\n\n# Fuente: pág. 7')[0] + '\n'
    expect(validate(sinRN004)).toMatchObject({ valid: true })
    // O se decide que no se contradicen y se borra el comentario
    expect(validate(r.content.replace(/^# CONTRADICCIÓN.*\n/gm, ''))).toMatchObject({ valid: true })
  })
})
