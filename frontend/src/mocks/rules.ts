/**
 * Reglas de negocio simuladas (backend/app/analyses/reglas.py y app/projects/reglas.py).
 * `r1` (api-pagos) trae su reglas_negocio.toml; los demás repos no tienen y pueden cargarlas desde Configuración.
 */
import type { BusinessRuleResult, BusinessRules, ProjectRules, RulePreview, RulesValidation } from '@/features/rules/types'
import type { Severity } from '@/shared/types/common'
import { getRepo } from './db'

const FILENAME = 'reglas_negocio.toml'
const APP_SOURCE = 'Configuración (cargadas en la app)'

const REPO_RULES: Record<string, string> = {
  r1: `# reglas_negocio.toml — reglas de negocio de api-pagos
[proyecto]
nombre  = "API de pagos"
version = "1.0"

[[regla]]
id          = "RN-001"
titulo      = "Montos con Decimal"
descripcion = "Todo monto de dinero se calcula con Decimal; nunca con float."
severidad   = "alta"
rutas       = ["pagos/"]
prohibido   = 'float\\('

[[regla]]
id          = "RN-002"
titulo      = "Consultas SQL parametrizadas"
descripcion = "Ninguna consulta SQL se arma concatenando datos del cliente."
severidad   = "alta"
rutas       = ["api.py"]
prohibido   = '(SELECT|INSERT|UPDATE|DELETE)[^"]*"\\s*\\+'

[[regla]]
id          = "RN-003"
titulo      = "La clave de los tokens viene del entorno"
descripcion = "La clave con la que se firman los tokens se lee de una variable de entorno."
severidad   = "media"
rutas       = ["auth.py"]
obligatorio = 'os\\.(environ|getenv)'

[[regla]]
id          = "RN-004"
titulo      = "Pagos sobre el límite requieren autorización"
descripcion = "Un pago mayor al límite solo se cobra si lo autorizó alguien de admin o finanzas."
severidad   = "alta"

[[regla]]
id          = "RN-005"
titulo      = "Reembolsos solo de pagos cobrados"
descripcion = "Un reembolso solo procede si el pago está en estado cobrado."
severidad   = "media"
`,
}

/** Resultado del último análisis de r1: patrones y pruebas (como si hubiera corrido en el sandbox). */
const R1_RESULTS: BusinessRuleResult[] = [
  {
    id: 'RN-001', title: 'Montos con Decimal', description: 'Todo monto de dinero se calcula con Decimal; nunca con float.', severity: 'alta',
    paths: ['pagos/'], forbidden: 'float\\(', required: null, story: 'HU-02', owner: 'Equipo backend',
    criterion: 'Dado un pago de $0.10 con comisión de 10 %, cuando se cobra, entonces el monto es exactamente $0.09',
    status: 'cumple', level: 'patron', detail: '`prohibido` no aparece (2 archivo(s) revisado(s))', evidence: [], evidence_total: 0, tests: [],
  },
  {
    id: 'RN-002', title: 'Consultas SQL parametrizadas', description: 'Ninguna consulta SQL se arma concatenando datos del cliente.', severity: 'alta',
    paths: ['api.py'], forbidden: '(SELECT|INSERT|UPDATE|DELETE)[^"]*"\\s*\\+', required: null, story: 'HU-05', owner: 'Equipo backend', criterion: null,
    status: 'no_cumple', level: 'patron', detail: '`prohibido` aparece en 1 línea(s)',
    evidence: [{ file: 'api.py', line: 17, text: 'query = "SELECT * FROM pagos WHERE id = " + pago_id' }], evidence_total: 1, tests: [],
  },
  {
    id: 'RN-003', title: 'La clave de los tokens viene del entorno', description: 'La clave con la que se firman los tokens se lee de una variable de entorno.', severity: 'media',
    paths: ['auth.py'], forbidden: null, required: 'os\\.(environ|getenv)', story: 'HU-01', owner: null, criterion: null,
    status: 'no_cumple', level: 'patron', detail: 'falta `obligatorio` en 1 de 1 archivo(s) con código',
    evidence: [{ file: 'auth.py', line: 1, text: 'no aparece `os\\.(environ|getenv)`' }], evidence_total: 1, tests: [],
  },
  {
    id: 'RN-004', title: 'Pagos sobre el límite requieren autorización', description: 'Un pago mayor al límite solo se cobra si lo autorizó alguien de admin o finanzas.', severity: 'alta',
    paths: [], forbidden: null, required: null, story: 'HU-03', owner: null,
    criterion: 'Dado un pago de $5,000 con límite de $1,000 autorizado por «ventas», cuando se procesa, entonces se rechaza con motivo «autorizador»',
    status: 'cumple', level: 'pruebas', detail: '1 prueba(s) pasan', evidence: [], evidence_total: 0,
    tests: [{ name: 'tests/test_procesador.py::test_rn004_pago_sobre_el_limite_requiere_autorizador_valido', file: 'tests/test_procesador.py', line: 15, outcome: 'passed', message: '' }],
  },
  {
    id: 'RN-005', title: 'Reembolsos solo de pagos cobrados', description: 'Un reembolso solo procede si el pago está en estado cobrado.', severity: 'media',
    paths: [], forbidden: null, required: null, story: null, owner: null, criterion: null,
    status: 'sin_verificar', level: 'ninguno',
    detail: 'Sin patrón ni pruebas: agrega `prohibido` u `obligatorio`, o una prueba con @pytest.mark.regla("RN-005") (o llamada test_rn005_…).',
    evidence: [], evidence_total: 0, tests: [],
  },
]

const uploads = new Map<string, { content: string; updated_at: string }>()

// ─── Validación (la del backend es la real; esta cubre los errores comunes) ───

interface ParsedRule extends RulePreview {
  description: string
}

class RulesError extends Error {}

const value = (block: string, key: string) => new RegExp(`^\\s*${key}\\s*=\\s*(?:"([^"]*)"|'([^']*)')`, 'm').exec(block)?.slice(1).find((v) => v !== undefined)

function parse(text: string): { project: string; rules: ParsedRule[] } {
  const lines = text.split('\n')
  const starts = lines.flatMap((l, i) => (/^\s*\[\[\s*regla\s*\]\]/.test(l) ? [i] : []))
  const head = lines.slice(0, starts[0] ?? lines.length).join('\n')
  if (!/^\s*\[proyecto\]/m.test(head)) throw new RulesError(`${FILENAME}: falta la sección [proyecto] con su \`nombre\``)
  const project = value(head, 'nombre')
  if (!project) throw new RulesError('[proyecto]: falta `nombre`')
  const seen = new Set<string>()
  const rules = starts.map((start, i) => {
    const block = lines.slice(start + 1, starts[i + 1] ?? lines.length).join('\n')
    const where = `línea ${start + 1}`
    for (const key of ['id', 'titulo', 'descripcion', 'severidad']) if (!value(block, key)) throw new RulesError(`${where}: falta \`${key}\``)
    const id = value(block, 'id')!
    if (!/^RN-\d{3}$/.test(id)) throw new RulesError(`${where}: \`${id}\` no cumple el formato \`RN-###\` (p. ej. RN-001)`)
    if (seen.has(id)) throw new RulesError(`${where}: ${id} está repetida`)
    seen.add(id)
    const severity = value(block, 'severidad')!
    if (!['alta', 'media', 'baja'].includes(severity)) throw new RulesError(`${where} · ${id}: \`severidad\` debe ser alta, media o baja (no «${severity}»)`)
    return {
      id, title: value(block, 'titulo')!, description: value(block, 'descripcion')!, severity: severity as Severity,
      pattern: Boolean(value(block, 'prohibido') ?? value(block, 'obligatorio')),
    }
  })
  return { project, rules }
}

export function validate(content: string): RulesValidation {
  try {
    const { project, rules } = parse(content)
    return { valid: true, error: null, project, rules: rules.map(({ id, title, severity, pattern }) => ({ id, title, severity, pattern })) }
  } catch (e) {
    if (e instanceof RulesError) return { valid: false, error: e.message, project: null, rules: [] }
    throw e
  }
}

// ─── API ───

export function projectRules(repoId: string): ProjectRules {
  const repo = getRepo(repoId)
  const own = REPO_RULES[repoId]
  const up = uploads.get(repoId)
  return {
    active: own ? 'repo' : up ? 'app' : null,
    repo: own ? { ...validate(own), content: own, path: FILENAME } : null,
    uploaded: up ? { ...validate(up.content), ...up } : null,
    cloned: repo.reports.length > 0,
    commit: repo.reports.at(-1)?.commit ?? null,
  }
}

/** Un texto = el contenido no es válido (el handler responde 422 con ese mensaje). */
export function upload(repoId: string, content: string): ProjectRules | string {
  getRepo(repoId)
  const check = validate(content)
  if (!check.valid) return check.error ?? 'Reglas no válidas'
  uploads.set(repoId, { content, updated_at: new Date().toISOString() })
  return projectRules(repoId)
}

export function remove(repoId: string): ProjectRules {
  getRepo(repoId)
  uploads.delete(repoId)
  return projectRules(repoId)
}

export function reportRules(repoId: string, reportId: string): BusinessRules {
  const repo = getRepo(repoId)
  const report = reportId === 'latest' ? repo.reports.at(-1) : repo.reports.find((r) => r.id === reportId)
  const base = { report_id: report?.id ?? reportId, checked: true, error: null, warnings: [] as string[] }
  const count = (rules: BusinessRuleResult[]) => ({
    total: rules.length,
    cumple: rules.filter((r) => r.status === 'cumple').length,
    no_cumple: rules.filter((r) => r.status === 'no_cumple').length,
    sin_verificar: rules.filter((r) => r.status === 'sin_verificar').length,
  })
  if (REPO_RULES[repoId])
    return {
      ...base, source: FILENAME, origin: 'repo', project: 'API de pagos', tests_ran: true, rules: R1_RESULTS, summary: count(R1_RESULTS),
      warnings: ['tests/test_api.py::test_reembolso usa RN-099, que no está en reglas_negocio.toml'],
    }
  const up = uploads.get(repoId)
  if (!up) return { ...base, source: null, origin: null, project: null, tests_ran: false, rules: [], summary: count([]) }
  const { project, rules } = parse(up.content)
  const results: BusinessRuleResult[] = rules.map((r) => ({
    id: r.id, title: r.title, description: r.description, severity: r.severity, paths: [], forbidden: null, required: null, story: null, owner: null, criterion: null,
    status: 'sin_verificar', level: 'ninguno', detail: 'Se verifica en el siguiente análisis.', evidence: [], evidence_total: 0, tests: [],
  }))
  return { ...base, source: APP_SOURCE, origin: 'app', project, tests_ran: false, rules: results, summary: count(results) }
}

export const TEMPLATE = REPO_RULES.r1.replace('API de pagos', 'Mi proyecto')
