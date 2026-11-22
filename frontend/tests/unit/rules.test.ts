import { describe, expect, it, vi } from 'vitest'
import type { BusinessRuleResult, HarnessView, MapSummary, PermissionMatrix, RulesPrecheck, RuleStatus, RulesValidation, RuleTestsView } from '@/features/rules/types'
import {
  baseName, EVIDENCE, fileToBase64, filterRules, githubRepo, harnessStatus, isDocument, mapSummary, markedCells, matrixFromCode, matrixPayload, nextCell, OUTCOME,
  precheckView, RULE_TEST_STATE, smokeLabel, STATUS, STRENGTH, testFunction, testName, testsSummary,
} from '@/features/rules/utils/rules'
import * as ruleTests from '@/mocks/ruleTests'
import * as harness from '@/mocks/harness'
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
    expect(validate(base)).toEqual({ valid: true, error: null, project: 'Tienda', rules: [{ id: 'RN-001', title: 'T', severity: 'alta', pattern: false, description: 'D', tipo: null, status: 'aprobada', source: null, doubts: [], scenarios: [] }], warnings: [] })
  })

  it('lee el formato v2: tipo, estado, dudas y escenarios', () => {
    const v2 = base + ['tipo = "flujo"', 'estado = "borrador"', 'fuente = "§2"', 'dudas = ["¿Y si falta?"]', '', '  [[regla.escenario]]', '  dado = "a"', '  cuando = "b"', '  entonces = "c"', ''].join('\n')
    const rule = validate(v2).rules[0]
    expect(rule).toMatchObject({ tipo: 'flujo', status: 'borrador', source: '§2', doubts: ['¿Y si falta?'], scenarios: [{ given: 'a', when: 'b', then: 'c' }] })
  })

  it('no deja aprobar una regla con dudas abiertas', () => {
    const result = validate(base + 'dudas = ["¿?"]\n')
    expect(result.valid).toBe(false)
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

describe('mapa y arnés de pruebas', () => {
  const map: MapSummary = {
    framework: 'fastapi', frameworks: ['fastapi'], endpoints: 16, models: 1, schemas: 3, roles: ['cajero', 'gerente'], integrations: [], uses_time: false,
    entry: ['inventario.main:app'], warnings: [],
  }

  it('resume el mapa con plurales', () => {
    expect(mapSummary(map)).toBe('16 endpoints, 1 modelo y 2 roles')
    expect(mapSummary({ ...map, endpoints: 1, roles: [] })).toBe('1 endpoint, 1 modelo y 0 roles')
  })

  it('nombra cada comprobación de la prueba de humo por su fixture', () => {
    expect(smokeLabel('test_humo_como[cajero]')).toBe("como('cajero')")
    expect(smokeLabel('test_humo_crear[crear_producto]')).toBe('crear_producto()')
    expect(smokeLabel('test_humo_extras[reloj]')).toBe('reloj')
    expect(smokeLabel('test_humo_api')).toBe('api')
    expect(smokeLabel('otra')).toBe('otra')
  })

  it('simulado: proponer, probar (pasa), aprobar; editar invalida y un token roto falla con un solo aviso', () => {
    vi.useFakeTimers()
    try {
      const repo = 'r1'
      harness.removeHarness(repo)
      const view = harness.proposeHarness(repo)
      const h = view.harness!
      expect(view.map?.framework).toBe('fastapi')
      expect([h.origin, h.smoke, h.errors]).toEqual(['ia', 'pendiente', []])
      expect(h.fixtures).toEqual(['sesiones', 'api', 'como', 'crear_pago'])
      expect(harnessStatus(h)).toEqual({ label: 'Sin probar', tone: 'neutral' })
      // No se aprueba sin prueba de humo
      expect(harness.approveHarness(repo, 'Ana')).toMatch(/prueba de humo/)

      expect((harness.runSmoke(repo) as HarnessView).harness?.smoke).toBe('corriendo')
      vi.runAllTimers()
      const passed = harness.harnessView(repo).harness!
      expect([passed.smoke, passed.smoke_message]).toEqual(['paso', '6 comprobaciones pasaron'])
      const approved = harness.approveHarness(repo, 'Ana') as HarnessView
      expect([approved.ready, approved.harness?.approved_by, harnessStatus(approved.harness!).label]).toEqual([true, 'Ana', 'Aprobado'])

      const edited = harness.editHarness(repo, passed.code.replace('Bearer prueba-{rol}', 'Bearer otro-{rol}'))!
      expect([edited.harness?.origin, edited.harness?.smoke, edited.ready]).toEqual(['manual', 'pendiente', false])
      harness.runSmoke(repo)
      vi.runAllTimers()
      const failed = harness.harnessView(repo).harness!
      expect(failed.smoke).toBe('fallo')
      expect(failed.smoke_message).toBe("como('cliente'): AssertionError: como('cliente'): GET /pagos respondió 401, el usuario no quedó autenticado (y 4 más)")

      // Con errores de validación no corre
      harness.editHarness(repo, 'import subprocess\n')
      expect(harness.runSmoke(repo)).toMatch(/^Corrige el arnés antes de probarlo: Falta el fixture `api`/)
      harness.removeHarness(repo)
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('pruebas de las reglas (simuladas)', () => {
  it('generar, correr y aprobar: las rotas no se aprueban y el resumen cuenta cada estado', () => {
    vi.useFakeTimers()
    try {
      const repo = 'r1'
      harness.removeHarness(repo)
      expect(ruleTests.generateTests(repo, null)).toMatch(/Aprueba el arnés/)
      harness.proposeHarness(repo)
      harness.runSmoke(repo)
      vi.runAllTimers()
      harness.approveHarness(repo, 'Ana')

      const start = ruleTests.ruleTestsView(repo)
      expect(start.harness_ready && start.can_generate).toBe(true)
      const total = start.rules.length
      expect(testsSummary(start)).toMatchObject({ missing: total, approved: 0, runnable: 0, approvable: [] })

      expect((ruleTests.generateTests(repo, null) as RuleTestsView).busy?.kind).toBe('generando')
      vi.runAllTimers()
      const drafts = ruleTests.ruleTestsView(repo)
      expect(drafts.busy).toBeNull()
      expect(testsSummary(drafts)).toMatchObject({ missing: 0, drafts: total, runnable: total, approvable: [] })
      expect(drafts.rules[0].test?.blocked).toBe('Córrela primero en el sandbox')

      // Una prueba editada que usa preparar sin pedirlo sale rota y no se puede aprobar
      const first = drafts.rules[0]
      ruleTests.editTest(repo, first.id, first.test!.code.replace(', preparar)', ')'))
      ruleTests.runTests(repo, null)
      vi.runAllTimers()
      const ran = ruleTests.ruleTestsView(repo)
      expect(ran.rules[0].test?.run?.verdict).toBe('prueba_rota')
      expect(ran.rules[1].test?.run?.verdict).toBe('no_cumple')
      const ok = testsSummary(ran).approvable
      expect(ok).not.toContain(first.id)
      expect(ok).toHaveLength(total - 1)

      const approved = ruleTests.approveTests(repo, ran.rules.map((r) => r.id), 'Ana')
      expect(approved.messages).toEqual([`${first.id}: La prueba está rota: corrígela o vuelve a generarla`])
      expect(testsSummary(approved)).toMatchObject({ approved: total - 1, drafts: 1 })
      expect(RULE_TEST_STATE[approved.rules[1].state].label).toBe('Aprobada')
      for (const r of approved.rules) ruleTests.removeTest(repo, r.id)
      harness.removeHarness(repo)
    } finally {
      vi.useRealTimers()
    }
  })

  it('los estados nuevos del reporte se ordenan después de no cumple', () => {
    const order = (['no_cumple', 'no_implementada', 'prueba_rota', 'sin_verificar', 'cumple', 'fuera_del_codigo'] as const).map((s) => STATUS[s].order)
    expect(order).toEqual([...order].sort((a, b) => a - b))
    expect(OUTCOME.broken.label).toBe('Rota')
  })
})

describe('matriz de permisos, evidencia y prueba de fuerza (fase 5)', () => {
  const matrix = (): PermissionMatrix => ({
    rule_id: 'RN-001', roles: ['cliente', 'admin'], saved: false,
    actions: [
      { id: 'POST /servicios', method: 'POST', path: '/servicios', function: 'app:crear', suggested: ['admin'], cells: {} },
      { id: 'POST /citas', method: 'POST', path: '/citas', function: 'app:reservar', suggested: [], cells: { cliente: 'permitido' } },
    ],
  })

  it('las celdas van de vacía a permitido, prohibido y otra vez vacía', () => {
    expect([nextCell(undefined), nextCell('permitido'), nextCell('prohibido')]).toEqual(['permitido', 'prohibido', undefined])
  })

  it('lo que se guarda lleva todas las celdas (null = fuera de la matriz) y se cuentan las marcadas', () => {
    const m = matrix()
    expect(matrixPayload(m)).toEqual({ 'POST /servicios': { cliente: null, admin: null }, 'POST /citas': { cliente: 'permitido', admin: null } })
    expect(markedCells(m)).toBe(1)
    // «Usar lo que hace el código» solo llena las acciones de las que el mapa sabe los roles
    const fromCode = matrixFromCode(m)
    expect(fromCode.actions[0].cells).toEqual({ cliente: 'prohibido', admin: 'permitido' })
    expect(fromCode.actions[1].cells).toEqual({ cliente: 'permitido' })
    expect(markedCells(fromCode)).toBe(3)
  })

  it('matriz → prueba sin IA, evidencia y prueba de fuerza en los mocks', () => {
    vi.useFakeTimers()
    try {
      const repo = 'r1'
      harness.proposeHarness(repo)
      harness.runSmoke(repo)
      vi.runAllTimers()
      harness.approveHarness(repo, 'Ana')
      const ruleId = ruleTests.ruleTestsView(repo).rules[0].id

      const m = ruleTests.getMatrix(repo, ruleId)
      expect(m.saved).toBe(false)
      expect(ruleTests.saveMatrix(repo, ruleId, matrixPayload(m))).toMatch(/Marca al menos una celda/)
      const view = ruleTests.saveMatrix(repo, ruleId, matrixPayload(matrixFromCode(m))) as RuleTestsView
      const test = view.rules[0].test!
      expect([test.origin, test.tipo, test.has_matrix, view.rules[0].permissions]).toEqual(['matriz', 'permisos', true, true])
      expect(test.code).toContain(`@pytest.mark.regla("${ruleId}")`)
      expect(ruleTests.getMatrix(repo, ruleId).saved).toBe(true)
      // La fuerza solo aplica a pruebas que pasan
      expect(test.strength_blocked).toBe('Córrela primero en el sandbox')
      expect(ruleTests.strengthTests(repo, null)).toMatch(/No hay pruebas que pasen/)

      ruleTests.runTests(repo, null)
      vi.runAllTimers()
      expect(testsSummary(ruleTests.ruleTestsView(repo)).measurable).toBe(1)
      expect((ruleTests.strengthTests(repo, null) as RuleTestsView).busy?.kind).toBe('fuerza')
      vi.runAllTimers()
      const measured = ruleTests.ruleTestsView(repo)
      expect(measured.rules[0].test?.strength?.status).toBe('fuerte')
      expect(STRENGTH.debil.label).toBe('Prueba débil')

      // Una prueba que solo revisa que no haya un 500 sale débil
      ruleTests.editTest(repo, ruleId, test.code.replace('assert r.status_code not in (401, 403)', 'assert r.status_code < 500'))
      ruleTests.runTests(repo, [ruleId])
      vi.runAllTimers()
      ruleTests.strengthTests(repo, [ruleId])
      vi.runAllTimers()
      const weak = ruleTests.ruleTestsView(repo)
      expect(weak.rules[0].test?.strength?.status).toBe('debil')
      expect(testsSummary(weak).weak).toBe(1)

      const explained = ruleTests.explainRule(repo, ruleId)
      expect(explained.rules[0].evidence?.verdict).toBe('implementada')
      expect(EVIDENCE[explained.rules[0].evidence!.verdict].label).toBe('Parece implementada')
      ruleTests.removeTest(repo, ruleId)
      harness.removeHarness(repo)
    } finally {
      vi.useRealTimers()
    }
  })
})
