/**
 * Pruebas de las reglas generadas por IA voy, simuladas (backend: app.projects.pruebas, PROPUESTA §6.3 y §9).
 * Generar escribe una prueba por regla cada ~0.5 s; correrlas tarda unos segundos. Las reglas en posición 2, 5, 8…
 * salen «no cumple» (como un código con reglas rotas) y una prueba sin `preparar` en la firma sale rota.
 */
import type { GeneratedTest, MatrixCell, PermissionMatrix, RuleTestRow, RuleTestsView, StrengthResult, SupportEvidence } from '@/features/rules/types'
import { crosscheck } from '@/features/rules/utils/rules'
import { harnessView } from './harness'
import { projectRules } from './rules'

const GENERATE_MS = 500
const RUN_MS = 2500
const STRENGTH_MS = 3000

interface Busy {
  kind: 'generando' | 'corriendo' | 'fuerza'
  total: number
  done: number
  current: string | null
}

const tests = new Map<string, Map<string, GeneratedTest>>()
const busy = new Map<string, Busy>()
const messages = new Map<string, string[]>()
const evidences = new Map<string, Map<string, SupportEvidence>>()
const matrices = new Map<string, Map<string, PermissionMatrix>>()

const now = () => new Date().toISOString().replace(/\.\d+Z$/, 'Z')
const slug = (title: string) => title.normalize('NFKD').replace(/[^\w\s]/g, '').toLowerCase().trim().replace(/\s+/g, '_').slice(0, 40)
const repoTests = (repoId: string) => tests.get(repoId) ?? tests.set(repoId, new Map()).get(repoId)!

function rulesOf(repoId: string) {
  const p = projectRules(repoId)
  const file = p.active === 'repo' ? p.repo : p.active === 'app' ? p.uploaded : null
  return file?.valid ? file.rules : []
}

function codeFor(id: string, title: string): string {
  const n = id.replace('-', '').toLowerCase()
  return `import pytest


@pytest.mark.regla("${id}")
def test_${n}_${slug(title)}(como, crear_pago, preparar):
    pago = crear_pago(monto="1500.00")
    preparar(pago["estado"] == "pendiente", f"el pago no quedó pendiente: {pago}")
    r = como("ventas").post(f"/pagos/{pago['id']}/cobrar")
    assert r.status_code in (400, 409, 422), f"${title}: se esperaba un rechazo, llegó {r.status_code}"
`
}

/** Corrida «simulada»: depende de la regla y de que la prueba pida `preparar` si lo usa. */
function verdictFor(index: number, test: GeneratedTest): NonNullable<GeneratedTest['run']> {
  const name = test.tests[0] ?? 'test'
  if (/preparar\(/.test(test.code) && !/def test_\w+\([^)]*preparar/.test(test.code))
    return { verdict: 'prueba_rota', detail: '1 de 1 prueba(s) rota(s): fallan al preparar el escenario, no por el código. Revisa la prueba', tests: [{ name, outcome: 'broken', message: "NameError: name 'preparar' is not defined" }] }
  if (index % 3 === 1)
    return { verdict: 'no_cumple', detail: '1 de 1 prueba(s) falla(n)', tests: [{ name, outcome: 'failed', message: 'AssertionError: se esperaba un rechazo, llegó 201' }] }
  return { verdict: 'cumple', detail: '1 prueba(s) pasan', tests: [{ name, outcome: 'passed', message: '' }] }
}

function check(test: GeneratedTest): GeneratedTest {
  const names = [...test.code.matchAll(/def (test_\w+)\(/g)].map((m) => m[1])
  const errors = test.kind === 'prueba' && !names.length ? ['No hay ninguna función de prueba (test_…)'] : []
  const blocked = test.kind !== 'prueba' ? null : errors.length ? 'Corrige los errores de la prueba' : !test.run ? 'Córrela primero en el sandbox' : test.run.verdict === 'prueba_rota' ? 'La prueba está rota: corrígela o vuelve a generarla' : null
  const strength_blocked = test.kind !== 'prueba' || test.outdated ? 'Solo para pruebas al día' : !test.run ? 'Córrela primero en el sandbox' : test.run.verdict !== 'cumple' ? 'Solo para pruebas que pasan: si la prueba falla, el código no cumple y no hay nada que medir' : null
  return { ...test, tests: names, errors, blocked, strength_blocked }
}

export function ruleTestsView(repoId: string): RuleTestsView {
  const h = harnessView(repoId)
  const rules = rulesOf(repoId)
  const stored = repoTests(repoId)
  const rows: RuleTestRow[] = rules.map((r) => {
    const t = stored.get(r.id)
    const test = t ? check(t) : null
    return {
      id: r.id, title: r.title, description: r.title, severity: r.severity, criterion: null, repo_tests: 0, test,
      state: !test ? 'sin_prueba' : test.approved ? 'aprobada' : 'borrador',
      permissions: /permis|\broles?\b|autoriz/i.test(r.title) || test?.tipo === 'permisos', evidence: evidences.get(repoId)?.get(r.id) ?? null,
      crosscheck: crosscheck(test?.run ?? null, evidences.get(repoId)?.get(r.id) ?? null),
    }
  })
  return {
    cloned: h.cloned, source: rules.length ? 'reglas_negocio.toml' : null, error: null, harness_ready: h.ready, can_generate: h.ready, can_explain: true, sandbox: true,
    rules: rows, busy: busy.get(repoId) ?? null, messages: messages.get(repoId) ?? [],
  }
}

/** Un texto = no se puede (el handler responde 409 con ese mensaje). */
export function generateTests(repoId: string, ids: string[] | null): RuleTestsView | string {
  if (busy.has(repoId)) return 'Espera: IA voy está trabajando en las pruebas de este proyecto'
  if (!harnessView(repoId).ready) return 'Aprueba el arnés de pruebas primero (Mapa y arnés de pruebas)'
  const stored = repoTests(repoId)
  const rules = rulesOf(repoId).filter((r) => (ids ? ids.includes(r.id) : !stored.has(r.id)))
  if (!rules.length) return 'Todas las reglas ya tienen prueba; elige cuáles volver a generar'
  const job: Busy = { kind: 'generando', total: rules.length, done: 0, current: rules[0].id }
  busy.set(repoId, job)
  messages.delete(repoId)
  rules.forEach((r, i) => {
    setTimeout(() => {
      stored.set(r.id, {
        kind: 'prueba', tipo: 'flujo', file: `tests/_ia_voy_reglas/test_${r.id.replace('-', '').toLowerCase()}_${slug(r.title)}.py`, code: codeFor(r.id, r.title),
        origin: 'ia', assumptions: ['Un pago se cobra con POST /pagos/{id}/cobrar'], endpoints: ['POST /pagos/{id}/cobrar'], reason: null, model: 'Gemini 3.8 Flash',
        errors: [], warnings: [], tests: [], outdated: false, run_status: 'pendiente', run: null, approved: false, approved_by: null, approved_at: null, blocked: null,
        updated_at: now(), strength_status: 'pendiente', strength: null, strength_blocked: null, has_matrix: false,
      })
      job.done = i + 1
      job.current = rules[i + 1]?.id ?? null
      if (job.done === job.total) busy.delete(repoId)
    }, GENERATE_MS * (i + 1))
  })
  return ruleTestsView(repoId)
}

export function runTests(repoId: string, ids: string[] | null): RuleTestsView | string {
  if (busy.has(repoId)) return 'Espera: IA voy está trabajando en las pruebas de este proyecto'
  const stored = repoTests(repoId)
  const rules = rulesOf(repoId)
  const chosen = rules.filter((r) => {
    const t = stored.get(r.id)
    return t && t.kind === 'prueba' && (ids ? ids.includes(r.id) : t.run_status === 'pendiente')
  })
  if (!chosen.length) return 'No hay pruebas válidas sin correr; elige cuáles volver a correr'
  for (const r of chosen) stored.set(r.id, { ...stored.get(r.id)!, run_status: 'corriendo', run: null })
  busy.set(repoId, { kind: 'corriendo', total: chosen.length, done: 0, current: null })
  setTimeout(() => {
    for (const r of chosen) {
      const t = check(stored.get(r.id)!)
      stored.set(r.id, { ...t, run_status: 'hecho', run: verdictFor(rules.indexOf(r), t) })
    }
    busy.delete(repoId)
  }, RUN_MS)
  return ruleTestsView(repoId)
}

export function approveTests(repoId: string, ids: string[], user: string): RuleTestsView {
  const stored = repoTests(repoId)
  const skipped: string[] = []
  for (const id of ids) {
    const t = stored.get(id)
    if (!t || t.approved) continue
    const blocked = check(t).blocked
    if (blocked) skipped.push(`${id}: ${blocked}`)
    else stored.set(id, { ...t, approved: true, approved_by: user, approved_at: now() })
  }
  messages.set(repoId, skipped)
  return ruleTestsView(repoId)
}

export function editTest(repoId: string, ruleId: string, code: string): RuleTestsView | null {
  const stored = repoTests(repoId)
  const t = stored.get(ruleId)
  if (!t) return null
  stored.set(ruleId, { ...t, code, kind: 'prueba', origin: 'manual', run_status: 'pendiente', run: null, approved: false, approved_by: null, approved_at: null, updated_at: now(), strength_status: 'pendiente', strength: null })
  return ruleTestsView(repoId)
}

export function removeTest(repoId: string, ruleId: string): RuleTestsView {
  repoTests(repoId).delete(ruleId)
  return ruleTestsView(repoId)
}

// ─── Fase 5: prueba de fuerza, evidencia y matriz de permisos ───

/** Fuerza «simulada»: las pruebas que solo miran que no haya un 500 salen débiles; las demás, fuertes o parciales. */
function strengthFor(index: number, test: GeneratedTest): StrengthResult {
  const at = { file: 'pagos/servicio.py', line: 42 + index }
  if (/status_code < 500/.test(test.code))
    return {
      status: 'debil', detail: 'La prueba siguió pasando con los 3 cambios: no verifica lo que dice la regla', killed: 0, total: 3, source: 'endpoint',
      survivors: [
        { ...at, description: '`monto > LIMITE` → `monto >= LIMITE`' },
        { ...at, description: 'se invierte la condición `monto > LIMITE`' },
        { ...at, line: at.line + 1, description: 'se quita `raise Rechazo(...)`' },
      ],
    }
  if (index % 2 === 1)
    return {
      status: 'parcial', detail: 'La prueba detectó 2 de 3 cambios; revisa los que no notó', killed: 2, total: 3, source: 'endpoint',
      survivors: [{ ...at, description: '`monto > LIMITE` → `monto >= LIMITE`' }],
    }
  return { status: 'fuerte', detail: 'La prueba detectó los 3 cambios a las líneas de la regla', killed: 3, total: 3, source: 'endpoint', survivors: [] }
}

/** Un texto = no se puede (el handler responde 409 con ese mensaje). */
export function strengthTests(repoId: string, ids: string[] | null): RuleTestsView | string {
  if (busy.has(repoId)) return 'Espera: IA voy está trabajando en las pruebas de este proyecto'
  const stored = repoTests(repoId)
  const rules = rulesOf(repoId)
  const chosen = rules.filter((r) => {
    const t = stored.get(r.id)
    return t && !check(t).strength_blocked && (ids ? ids.includes(r.id) : t.strength_status === 'pendiente')
  })
  if (!chosen.length) return 'No hay pruebas que pasen sin prueba de fuerza; elige cuáles volver a medir'
  for (const r of chosen) stored.set(r.id, { ...stored.get(r.id)!, strength_status: 'corriendo', strength: null })
  busy.set(repoId, { kind: 'fuerza', total: chosen.length, done: 0, current: null })
  setTimeout(() => {
    for (const r of chosen) {
      const t = stored.get(r.id)!
      stored.set(r.id, { ...t, strength_status: 'hecho', strength: strengthFor(rules.indexOf(r), t) })
    }
    busy.delete(repoId)
  }, STRENGTH_MS)
  return ruleTestsView(repoId)
}

export function explainRule(repoId: string, ruleId: string): RuleTestsView {
  const repo = evidences.get(repoId) ?? evidences.set(repoId, new Map()).get(repoId)!
  const i = rulesOf(repoId).findIndex((r) => r.id === ruleId)
  repo.set(ruleId, {
    verdict: i % 3 === 1 ? 'parcial' : 'implementada',
    summary: i % 3 === 1 ? 'Rechaza el cobro, pero con `>` donde la regla dice «a partir de».' : 'El servicio de pagos rechaza el cobro antes de llamar a la pasarela.',
    places: [{ file: 'pagos/servicio.py', start: 42 + i, end: 43 + i, why: 'aquí se revisa el límite de la regla' }],
    model: 'Gemini 3.8 Flash', search: ['indice', 'palabras'], created_at: now(), stale: false,
  })
  return ruleTestsView(repoId)
}

const ACTIONS: [string, string[]][] = [
  ['POST /pagos', ['cliente', 'ventas', 'admin']],
  ['POST /pagos/{pago_id}/cobrar', ['ventas', 'admin']],
  ['POST /pagos/{pago_id}/reembolsar', ['finanzas', 'admin']],
  ['PATCH /tarifas/{tarifa_id}', ['admin']],
  ['GET /reportes/cobros', ['finanzas', 'admin']],
]

export function getMatrix(repoId: string, ruleId: string): PermissionMatrix {
  const saved = matrices.get(repoId)?.get(ruleId)
  if (saved) return saved
  return {
    rule_id: ruleId, roles: ['cliente', 'ventas', 'finanzas', 'admin'], saved: false,
    actions: ACTIONS.map(([id, suggested]) => {
      const [method, path] = id.split(' ')
      return { id, method, path, function: `pagos.rutas:${path.split('/')[1]}`, suggested, cells: {} }
    }),
  }
}

/** La prueba de la matriz (la misma forma que app.projects.reglas_matriz). Un texto = no se puede. */
export function saveMatrix(repoId: string, ruleId: string, cells: Record<string, Record<string, MatrixCell | null>>): RuleTestsView | string {
  if (!harnessView(repoId).ready) return 'Aprueba el arnés de pruebas primero (Mapa y arnés de pruebas)'
  const base = getMatrix(repoId, ruleId)
  const actions = base.actions.map((a) => ({
    ...a, cells: Object.fromEntries(Object.entries(cells[a.id] ?? {}).filter(([, v]) => v)) as Partial<Record<string, MatrixCell>>,
  }))
  const cases = actions.flatMap((a) => Object.entries(a.cells).map(([rol, v]) => [a.id, rol, v === 'permitido'] as const))
  if (!cases.length) return 'Marca al menos una celda como «permitido» o «prohibido»'
  ;(matrices.get(repoId) ?? matrices.set(repoId, new Map()).get(repoId)!).set(ruleId, { ...base, actions, saved: true })
  const rule = rulesOf(repoId).find((r) => r.id === ruleId)
  const n = ruleId.replace('-', '').toLowerCase()
  const rows = cases.map(([a, r, ok]) => `    ('${a}', '${r}', ${ok ? 'True' : 'False'}),`).join('\n')
  const code = [
    'import re', '', 'import pytest', '', 'CASOS = [', rows, ']', '', '',
    `@pytest.mark.regla("${ruleId}")`,
    '@pytest.mark.parametrize(("accion", "rol", "permitido"), CASOS)',
    `def test_${n}_matriz_de_permisos(como, preparar, accion, rol, permitido):`,
    '    metodo, plantilla = accion.split(" ", 1)',
    '    ruta = re.sub(r"[{][^}]*[}]", "999999", plantilla)',
    '    r = getattr(como(rol), metodo.lower())(ruta, json={})',
    '    if permitido:',
    '        assert r.status_code not in (401, 403)',
    '    else:',
    '        assert r.status_code in (401, 403)',
    '',
  ].join('\n')
  repoTests(repoId).set(ruleId, {
    kind: 'prueba', tipo: 'permisos', file: `tests/_ia_voy_reglas/test_${n}_${slug(rule?.title ?? 'permisos')}.py`, code, origin: 'matriz',
    assumptions: [`La matriz del equipo: ${cases.length} celdas`], endpoints: actions.filter((a) => Object.keys(a.cells).length).map((a) => a.id),
    reason: null, model: null, errors: [], warnings: [], tests: [], outdated: false, run_status: 'pendiente', run: null, approved: false,
    approved_by: null, approved_at: null, blocked: null, updated_at: now(), strength_status: 'pendiente', strength: null, strength_blocked: null, has_matrix: true,
  })
  return ruleTestsView(repoId)
}
