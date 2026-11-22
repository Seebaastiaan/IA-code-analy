/**
 * Reglas de negocio simuladas (backend/app/analyses/reglas.py y app/projects/reglas.py).
 * `r1` (api-pagos) trae su reglas_negocio.toml; los demás repos no tienen y pueden cargarlas desde Configuración.
 * En la revisión de Nuevo análisis, `ana-lopez/scraper-precios` (aún no es proyecto) trae un archivo con errores, y
 * los repos CRUD de prueba (fixtures/crudRules.ts) traen su archivo real.
 */
import type { BusinessRuleResult, BusinessRules, ImportedRules, ImportRulesRequest, ProjectRules, RuleApproval, RulePreview, RulesPrecheck, RulesValidation } from '@/features/rules/types'
import type { Severity } from '@/shared/types/common'
import { findRepoByName, getRepo } from './db'
import { CRUD_REPOS } from './fixtures/crudRules'
import { repos as githubRepos } from './github'

const FILENAME = 'reglas_negocio.toml'
const APP_SOURCE = 'Configuración (cargadas en la app)'
const MAX_WARNINGS = 20

const REPO_RULES: Record<string, string> = {
  r1: `# reglas_negocio.toml — reglas de negocio de api-pagos (formato de IA VOY)
#
# Cada regla dice, en palabras del negocio, qué debe pasar siempre. IA VOY la comprueba de una de dos formas:
#   - con una PRUEBA marcada @pytest.mark.regla("RN-00X") (o llamada test_rn00X_…) que simula el criterio;
#   - con un PATRÓN: un texto que NO debe aparecer en el código (prohibido) o que SÍ debe aparecer (obligatorio).

[proyecto]
nombre  = "API de pagos"
version = "1.0"

[[regla]]
id          = "RN-001"
titulo      = "Los cobros salen exactos al centavo"
descripcion = "Lo que se cobra coincide al centavo con lo calculado: a un pago de $0.10 se le quita 10 % de comisión y quedan exactamente $0.09, ni un centavo más ni menos."
severidad   = "alta"
rutas       = ["pagos/"]
# PATRÓN: en pagos/ no debe aparecer  float(  ; float pierde centavos. El dinero se maneja con Decimal.
prohibido   = 'float\\('
criterio    = "Dado un pago de $0.10 con comisión de 10 %, cuando se cobra, entonces el monto es exactamente $0.09"

[[regla]]
id          = "RN-002"
titulo      = "Lo que manda el cliente no puede alterar la consulta de pagos"
descripcion = "El nombre del cliente que llega en la petición se usa solo como dato. Si se pegara dentro de la consulta, alguien podría mandar ' OR '1'='1 y ver los pagos de todos los clientes."
severidad   = "alta"
rutas       = ["api.py"]
# PATRÓN: no debe aparecer una consulta (SELECT, INSERT…) a la que se le pega texto con +
prohibido   = '(SELECT|INSERT|UPDATE|DELETE)[^"]*"\\s*\\+'

[[regla]]
id          = "RN-003"
titulo      = "La clave secreta de los tokens no está escrita en el código"
descripcion = "La clave con la que se firman las sesiones se lee del servidor (variable de entorno). Si estuviera en el código, cualquiera con acceso al repositorio podría hacerse pasar por un cliente."
severidad   = "media"
rutas       = ["auth.py"]
# PATRÓN: auth.py debe leer la clave con  os.environ  u  os.getenv
obligatorio = 'os\\.(environ|getenv)'

[[regla]]
id          = "RN-004"
titulo      = "Un pago mayor al límite necesita autorización de admin o finanzas"
descripcion = "Un pago que pasa el límite del cliente solo se cobra si lo autorizó alguien de administración o de finanzas; si lo autorizó otra área, se rechaza."
severidad   = "alta"
criterio    = "Dado un pago de $5,000 con límite de $1,000 autorizado por «ventas», cuando se procesa, entonces se rechaza con motivo «autorizador»"
# Se verifica con la prueba test_rn004_pago_sobre_el_limite_requiere_autorizador_valido

[[regla]]
id          = "RN-005"
titulo      = "Solo se reembolsa un pago que ya se cobró"
descripcion = "Un pago pendiente o rechazado no se puede reembolsar: no hay dinero que regresar."
severidad   = "media"
criterio    = "Dado un pago pendiente de $300, cuando se pide su reembolso, entonces se rechaza"
# Todavía sin prueba ni patrón: queda "sin verificar"
`,
}

const TEMPLATE = REPO_RULES.r1.replace('API de pagos', 'Mi proyecto')

/** Resultado del último análisis de r1: patrones y pruebas (como si hubiera corrido en el sandbox). */
const R1_RESULTS: BusinessRuleResult[] = [
  {
    id: 'RN-001', title: 'Los cobros salen exactos al centavo',
    description: 'Lo que se cobra coincide al centavo con lo calculado: a un pago de $0.10 se le quita 10 % de comisión y quedan exactamente $0.09, ni un centavo más ni menos.', severity: 'alta',
    paths: ['pagos/'], forbidden: 'float\\(', required: null, story: 'HU-02', owner: 'Equipo backend',
    criterion: 'Dado un pago de $0.10 con comisión de 10 %, cuando se cobra, entonces el monto es exactamente $0.09',
    status: 'cumple', level: 'patron', detail: '`prohibido` no aparece (2 archivo(s) revisado(s))', evidence: [], evidence_total: 0, tests: [],
  },
  {
    id: 'RN-002', title: 'Lo que manda el cliente no puede alterar la consulta de pagos',
    description: "El nombre del cliente que llega en la petición se usa solo como dato. Si se pegara dentro de la consulta, alguien podría mandar ' OR '1'='1 y ver los pagos de todos los clientes.", severity: 'alta',
    paths: ['api.py'], forbidden: '(SELECT|INSERT|UPDATE|DELETE)[^"]*"\\s*\\+', required: null, story: 'HU-05', owner: 'Equipo backend', criterion: null,
    status: 'no_cumple', level: 'patron', detail: '`prohibido` aparece en 1 línea(s)',
    evidence: [{ file: 'api.py', line: 17, text: `consulta = "SELECT * FROM pagos WHERE cliente = '" + cliente + "'"` }], evidence_total: 1, tests: [],
  },
  {
    id: 'RN-003', title: 'La clave secreta de los tokens no está escrita en el código',
    description: 'La clave con la que se firman las sesiones se lee del servidor (variable de entorno). Si estuviera en el código, cualquiera con acceso al repositorio podría hacerse pasar por un cliente.', severity: 'media',
    paths: ['auth.py'], forbidden: null, required: 'os\\.(environ|getenv)', story: 'HU-01', owner: null, criterion: null,
    status: 'no_cumple', level: 'patron', detail: 'falta `obligatorio` en 1 de 1 archivo(s) con código',
    evidence: [{ file: 'auth.py', line: 1, text: 'no aparece `os\\.(environ|getenv)`' }], evidence_total: 1, tests: [],
  },
  {
    id: 'RN-004', title: 'Un pago mayor al límite necesita autorización de admin o finanzas',
    description: 'Un pago que pasa el límite del cliente solo se cobra si lo autorizó alguien de administración o de finanzas; si lo autorizó otra área, se rechaza.', severity: 'alta',
    paths: [], forbidden: null, required: null, story: 'HU-03', owner: null,
    criterion: 'Dado un pago de $5,000 con límite de $1,000 autorizado por «ventas», cuando se procesa, entonces se rechaza con motivo «autorizador»',
    status: 'cumple', level: 'pruebas', detail: '1 prueba(s) pasan', evidence: [], evidence_total: 0,
    tests: [{ name: 'tests/test_procesador.py::test_rn004_pago_sobre_el_limite_requiere_autorizador_valido', file: 'tests/test_procesador.py', line: 15, outcome: 'passed', message: '' }],
  },
  {
    id: 'RN-005', title: 'Solo se reembolsa un pago que ya se cobró', description: 'Un pago pendiente o rechazado no se puede reembolsar: no hay dinero que regresar.', severity: 'media',
    paths: [], forbidden: null, required: null, story: null, owner: null, criterion: 'Dado un pago pendiente de $300, cuando se pide su reembolso, entonces se rechaza',
    status: 'sin_verificar', level: 'ninguno',
    detail: 'Sin patrón ni pruebas: agrega `prohibido` u `obligatorio`, o una prueba con @pytest.mark.regla("RN-005") (o llamada test_rn005_…).',
    evidence: [], evidence_total: 0, tests: [],
  },
]

const uploads = new Map<string, { content: string; updated_at: string }>()

// ─── Validación (la del backend es la real; esta sigue su orden y sus mensajes en los errores comunes) ───

interface ParsedRule extends RulePreview {
  description: string
  paths: string[]
  forbidden: string | null
  required: string | null
}

class RulesError extends Error {}

const PROJECT_FIELDS = ['nombre', 'version', 'formato']
const KINDS = ['datos', 'flujo', 'calculo', 'permisos', 'auditoria', 'integracion', 'proceso']
const RULE_FIELDS = ['criterio', 'descripcion', 'dudas', 'estado', 'fuente', 'historia', 'ia', 'id', 'obligatorio', 'prohibido', 'responsable', 'rutas', 'severidad', 'tipo', 'titulo']

const value = (block: string, key: string) => new RegExp(`^\\s*${key}\\s*=\\s*(?:"([^"]*)"|'([^']*)')`, 'm').exec(block)?.slice(1).find((v) => v !== undefined)
const keys = (block: string) => [...block.matchAll(/^\s*([A-Za-z_]+)\s*=/gm)].map((m) => m[1])

function pattern(block: string, key: string, where: string): string | null {
  const p = value(block, key)?.trim()
  if (!p) return null
  try {
    // Las banderas de Python al inicio ((?i)…) no las entiende todo navegador
    new RegExp(p.replace(/^\(\?[aiLmsux]+\)/, ''))
  } catch {
    throw new RulesError(`${where}: \`${key}\` no es una expresión regular válida`)
  }
  return p
}

function parse(text: string): { project: string; rules: ParsedRule[] } {
  const lines = text.split('\n')
  const starts = lines.flatMap((l, i) => (/^\s*\[\[\s*regla\s*\]\]/.test(l) ? [i] : []))
  const head = lines.slice(0, starts[0] ?? lines.length).join('\n')
  if (!/^\s*\[proyecto\]/m.test(head)) throw new RulesError(`${FILENAME}: falta la sección [proyecto] con su \`nombre\``)
  const extra = keys(head).filter((k) => !PROJECT_FIELDS.includes(k)).sort()
  if (extra.length) throw new RulesError(`[proyecto]: campo desconocido \`${extra[0]}\` (campos válidos: nombre, version)`)
  const project = value(head, 'nombre')
  if (!project) throw new RulesError('[proyecto]: falta `nombre`')
  const seen = new Set<string>()
  const rules = starts.map((start, i) => {
    const whole = lines.slice(start + 1, starts[i + 1] ?? lines.length).join('\n')
    // Los escenarios ([[regla.escenario]]) van después de los campos de la regla
    const [block, ...scenarioBlocks] = whole.split(/^\s*\[\[\s*regla\.escenario\s*\]\]/m)
    const where = `línea ${start + 1}`
    const unknown = keys(block).filter((k) => !RULE_FIELDS.includes(k)).sort()
    if (unknown.length) throw new RulesError(`${where}: campo desconocido \`${unknown[0]}\` (campos válidos: ${RULE_FIELDS.join(', ')})`)
    const id = value(block, 'id')
    if (!id) throw new RulesError(`${where}: falta \`id\``)
    if (!/^RN-\d{3}$/.test(id)) throw new RulesError(`${where}: \`${id}\` no cumple el formato \`RN-###\` (p. ej. RN-001)`)
    const ruleWhere = `${where} · ${id}`
    const severity = value(block, 'severidad')
    if (!severity) throw new RulesError(`${ruleWhere}: falta \`severidad\``)
    if (!['alta', 'media', 'baja'].includes(severity)) throw new RulesError(`${ruleWhere}: \`severidad\` debe ser alta, media o baja (no «${severity}»)`)
    if (/^\s*rutas\s*=\s*[^[\s]/m.test(block)) throw new RulesError(`${ruleWhere}: \`rutas\` debe ser una lista, p. ej. ["app/pagos/"]`)
    for (const key of ['titulo', 'descripcion']) if (!value(block, key)) throw new RulesError(`${ruleWhere}: falta \`${key}\``)
    const tipo = value(block, 'tipo')
    if (tipo && !KINDS.includes(tipo)) throw new RulesError(`${ruleWhere}: \`tipo\` debe ser ${KINDS.join(', ')} (no «${tipo}»)`)
    const status = value(block, 'estado') ?? 'aprobada'
    if (status !== 'borrador' && status !== 'aprobada') throw new RulesError(`${ruleWhere}: \`estado\` debe ser borrador o aprobada (no «${status}»)`)
    const doubts = [...(/^\s*dudas\s*=\s*\[(.*)\]\s*$/m.exec(block)?.[1] ?? '').matchAll(/"((?:[^"\\]|\\.)*)"/g)].map((m) => JSON.parse(`"${m[1]}"`) as string)
    if (status === 'aprobada' && doubts.length) throw new RulesError(`${ruleWhere}: está aprobada pero tiene dudas abiertas; resuélvelas o déjala en borrador`)
    const scenarios = scenarioBlocks.map((b) => ({ given: value(b, 'dado') ?? '', when: value(b, 'cuando') ?? '', then: value(b, 'entonces') ?? '' }))
    const forbidden = pattern(block, 'prohibido', ruleWhere)
    const required = pattern(block, 'obligatorio', ruleWhere)
    if (seen.has(id)) throw new RulesError(`${where}: ${id} está repetida`)
    seen.add(id)
    return {
      id, title: value(block, 'titulo')!, description: value(block, 'descripcion')!, severity: severity as Severity,
      pattern: Boolean(forbidden ?? required), forbidden, required,
      tipo: (tipo ?? null) as RulePreview['tipo'], status: status as RuleApproval, source: value(block, 'fuente') ?? null, doubts, scenarios,
      paths: [...(/^\s*rutas\s*=\s*\[([^\]]*)\]/m.exec(block)?.[1] ?? '').matchAll(/["']([^"']+)["']/g)].map((m) => m[1].replace(/^\.?\/+/, '')),
    }
  })
  checkMarkedContradictions(text, new Set(rules.map((r) => r.id)))
  return { project, rules }
}

/** `# CONTRADICCIÓN RN-002 RN-004: …` (lo escribe el importador): inválido mientras existan las dos reglas. */
function checkMarkedContradictions(text: string, ids: Set<string>) {
  text.split('\n').forEach((line, i) => {
    const m = /^\s*#\s*CONTRADICCI[OÓ]N\s+(RN-\d{3})\s+(?:y\s+)?(RN-\d{3})\s*:?\s*(.*)$/i.exec(line)
    if (!m) return
    const [a, b, reason] = [m[1].toUpperCase(), m[2].toUpperCase(), m[3].trim()]
    if (a !== b && ids.has(a) && ids.has(b)) {
      throw new RulesError(
        `línea ${i + 1}: ${a} y ${b} se contradicen según el documento${reason ? `: ${reason}` : ''}. Deja solo la regla que vale y borra el comentario «# CONTRADICCIÓN» (o bórralo si decides que no se contradicen)`,
      )
    }
  })
}

// ─── Contradicciones y duplicados (reglas.conflicts del backend) ───

const REGEX_META = new Set('.^$*+?{}[]|()')

/** Texto fijo que busca `pattern` (p. ej. `@requiere_admin`, `os\.getenv`); null si usa regex de verdad. */
function literal(pattern: string): string | null {
  let out = ''
  for (let i = 0; i < pattern.length; i++) {
    const c = pattern[i]
    if (c === '\\') {
      if (i + 1 >= pattern.length || /[A-Za-z0-9]/.test(pattern[i + 1])) return null
      out += pattern[++i]
    } else if (REGEX_META.has(c)) return null
    else out += c
  }
  return out || null
}

const inPath = (file: string, path: string) => {
  const p = path.replace(/^\/+|\/+$/g, '')
  return file === p || file.startsWith(`${p}/`)
}

const overlap = (a: string[], b: string[]) =>
  !a.length || !b.length || a.some((x) => b.some((y) => inPath(x.replace(/\/+$/, ''), y) || inPath(y.replace(/\/+$/, ''), x)))

const norm = (text: string) => text.toLowerCase().split(/\s+/).filter(Boolean).join(' ').replace(/[.;:]+$/, '')

function forcesForbidden(forbidden: string, required: string): boolean {
  if (forbidden === required) return true
  const lit = literal(required)
  if (lit === null) return false
  try {
    const re = new RegExp(forbidden.replace(/^\(\?[aiLmsux]+\)/, ''))
    return re.test(lit) && re.test(` ${lit} `)
  } catch {
    return false
  }
}

/** Avisos de reglas que se contradicen o que parecen duplicadas. No invalidan el archivo. */
export function conflicts(rules: ParsedRule[]): string[] {
  const out: string[] = []
  for (const a of rules)
    for (const b of rules) {
      if (!a.forbidden || !b.required || !overlap(a.paths, b.paths) || !forcesForbidden(a.forbidden, b.required)) continue
      out.push(a === b
        ? `${a.id} se contradice: \`obligatorio\` (\`${a.required}\`) siempre incluye lo \`prohibido\` (\`${a.forbidden}\`); nunca puede cumplirse`
        : `${a.id} y ${b.id} se contradicen: ${b.id} exige \`${b.required}\` y ${a.id} prohíbe \`${a.forbidden}\` en las mismas rutas; no pueden cumplirse las dos`)
    }
  rules.forEach((a, i) =>
    rules.slice(i + 1).forEach((b) => {
      const same: string[] = []
      const paths = (r: ParsedRule) => [...new Set(r.paths)].sort().join('\n')
      if ((a.forbidden || a.required) && a.forbidden === b.forbidden && a.required === b.required && paths(a) === paths(b)) same.push('el mismo patrón y rutas')
      if (norm(a.title) === norm(b.title)) same.push('el mismo título')
      if (norm(a.description) === norm(b.description)) same.push('la misma descripción')
      if (same.length) out.push(`${b.id} parece duplicada de ${a.id}: tiene ${same.join(' y ')}`)
    }),
  )
  return [...new Set(out)].slice(0, MAX_WARNINGS)
}

export function validate(content: string): RulesValidation {
  try {
    const { project, rules } = parse(content)
    return { valid: true, error: null, project, rules: rules.map(({ id, title, severity, pattern, description, tipo, status, source, doubts, scenarios }) => ({ id, title, severity, pattern, description, tipo, status, source, doubts, scenarios })), warnings: conflicts(rules) }
  } catch (e) {
    if (e instanceof RulesError) return { valid: false, error: e.message, project: null, rules: [] }
    throw e
  }
}

/** Validación contra los archivos de un repositorio: además de la sintaxis, que sus `rutas` existan en él. */
function withPaths(content: string, files: string[] | null, name: string): RulesValidation {
  const result = validate(content)
  // Sin los archivos del repo (no se pudo leer) las rutas no se revisan, como en el backend
  if (!result.valid || files === null) return result
  const missing = parse(content).rules.flatMap((r) => r.paths.filter((p) => !files.some((f) => inPath(f, p))).map((p) => `${r.id}: la ruta \`${p}\` no existe en ${name}`))
  return { ...result, warnings: [...(result.warnings ?? []), ...missing].slice(0, MAX_WARNINGS) }
}

/** Validación de las reglas de un proyecto: además de la sintaxis, que sus `rutas` existan en el repo (si ya se clonó). */
export function validateFor(repoId: string, content: string): RulesValidation {
  const repo = getRepo(repoId)
  return repo.reports.length === 0 ? validate(content) : withPaths(content, Object.keys(repo.content), repo.name)
}

/** Plantilla del proyecto: su nombre y una carpeta con código que existe en su repositorio. */
export function templateFor(repoId: string): string {
  const repo = getRepo(repoId)
  const folders = [...new Set(Object.keys(repo.content).filter((f) => f.endsWith('.py') && f.includes('/') && !f.startsWith('tests/')).map((f) => f.split('/')[0]))]
  const rutas = folders[0] ? `["${folders[0]}/"]` : '[]'
  return TEMPLATE.replace('nombre  = "Mi proyecto"', `nombre  = ${JSON.stringify(repo.name)}`)
    .replace('reglas de negocio de api-pagos', `reglas de negocio de ${repo.name}`)
    .replace('rutas       = ["pagos/"]', `rutas       = ${rutas}`)
    .replace('rutas       = ["api.py"]', 'rutas       = []')
    .replace('rutas       = ["auth.py"]', 'rutas       = []')
}

// ─── API ───

export function projectRules(repoId: string): ProjectRules {
  const repo = getRepo(repoId)
  const own = REPO_RULES[repoId]
  const up = uploads.get(repoId)
  return {
    active: own ? 'repo' : up ? 'app' : null,
    repo: own ? { ...validate(own), content: own, path: FILENAME } : null,
    uploaded: up ? { ...validateFor(repoId, up.content), ...up } : null,
    cloned: repo.reports.length > 0,
    commit: repo.reports.at(-1)?.commit ?? null,
    documents: repo.reports.length > 0 ? DOCUMENTS[repo.name] ?? [] : [],
    can_import: true,
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
    prueba_rota: rules.filter((r) => r.status === 'prueba_rota').length,
    no_implementada: rules.filter((r) => r.status === 'no_implementada').length,
    fuera_del_codigo: rules.filter((r) => r.status === 'fuera_del_codigo').length,
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
    id: r.id, title: r.title, description: r.description, severity: r.severity, paths: r.paths, forbidden: r.forbidden, required: r.required,
    story: null, owner: null, criterion: null,
    status: 'sin_verificar', level: 'ninguno', detail: 'Se verifica en el siguiente análisis.', evidence: [], evidence_total: 0, tests: [],
  }))
  return { ...base, source: APP_SOURCE, origin: 'app', project, tests_ran: false, rules: results, summary: count(results), warnings: conflicts(rules) }
}


// ─── Revisión al cargar el repo (Nuevo análisis) ───

/** Archivo de reglas (y archivos) de repos que todavía no son proyecto (los proyectos usan REPO_RULES). */
const PRECHECK_FILES: Record<string, { content: string; files: string[] }> = {
  'ana-lopez/scraper-precios': {
    content: `# reglas_negocio.toml — scraper-precios (con un error a propósito)
[proyecto]
nombre = "Scraper de precios"

[[regla]]
id          = "R1"
titulo      = "Los precios se guardan exactos al centavo"
descripcion = "El precio leído de la tienda se guarda tal cual, al centavo: $19.99 se guarda como $19.99, no como $19.989999."
severidad   = "alta"
rutas       = ["scraper/"]
prohibido   = 'float\\('
`,
    files: ['main.py', 'scraper/precios.py'],
  },
  ...CRUD_REPOS,
}

const REPO_URL = /^https:\/\/(?:www\.)?github\.com\/([A-Za-z0-9._-]+)\/([A-Za-z0-9._-]+?)(?:\.git)?\/?$/i

/** null = la URL no es de GitHub (el handler responde 422). */
export function precheck(url: string, _branch: string, content?: string): RulesPrecheck | null {
  const m = REPO_URL.exec(url.trim())
  if (!m) return null
  const name = `${m[1]}/${m[2]}`
  const project = findRepoByName(name)
  const known = project ? undefined : Object.entries(PRECHECK_FILES).find(([n]) => n.toLowerCase() === name.toLowerCase())?.[1]
  const files = project ? Object.keys(project.content) : known?.files ?? null
  const text = project ? REPO_RULES[project.id] : known?.content
  const reachable = Boolean(project || text || githubRepos(null).some((r) => r.full_name.toLowerCase() === name.toLowerCase()))
  const file = text ? { ...withPaths(text, files, name), content: text, path: FILENAME } : null
  const up = project ? uploads.get(project.id) : undefined
  const uploaded = project && up ? { ...withPaths(up.content, files, name), ...up } : null
  return {
    repo: name,
    status: !reachable ? 'unavailable' : !file ? 'missing' : file.valid ? 'valid' : 'invalid',
    message: reachable ? null : 'No se encontró el repositorio o la rama (o no tienes acceso). Las reglas se revisan al analizar.',
    file,
    project_id: project?.id ?? null,
    uploaded,
    active: file?.valid ? 'repo' : uploaded?.valid ? 'app' : file ? 'repo' : null,
    template: TEMPLATE.replace('nombre  = "Mi proyecto"', `nombre  = ${JSON.stringify(name)}`),
    checked: content === undefined ? null : withPaths(content, files, name),
    documents: reachable ? Object.entries(DOCUMENTS).find(([n]) => n.toLowerCase() === name.toLowerCase())?.[1] ?? [] : [],
    can_import: true,
  }
}


// ─── Importar desde un documento de requisitos (lo que respondería Gemini) ───

/** Documentos de requisitos de cada repo (los demás no tienen) */
const DOCUMENTS: Record<string, string[]> = {
  'equipo/bot-soporte': ['docs/Requerimientos.pdf'],
}

const IMPORTED_RULES = [
  {
    fuente: 'pág. 3 · §2.1', severidad: 'alta',
    titulo: 'Solo un agente de soporte puede cerrar un ticket',
    descripcion: 'Un ticket solo se marca como cerrado si lo cierra un agente de soporte; si lo intenta el cliente o el bot, se rechaza.',
    criterio: 'Dado un ticket abierto, cuando el bot intenta cerrarlo, entonces el ticket sigue abierto',
  },
  {
    fuente: 'pág. 4 · §2.3', severidad: 'media',
    titulo: 'Un ticket urgente se responde en menos de una hora',
    descripcion: 'Los tickets marcados como urgentes se asignan a un agente y reciben la primera respuesta en menos de 60 minutos.',
    criterio: null,
  },
  {
    fuente: 'pág. 5 · §3.1', severidad: 'alta',
    titulo: 'El bot no muestra datos personales de otros clientes',
    descripcion: 'Al responder, el bot solo usa los datos del cliente que escribe; nunca muestra correos, teléfonos ni tickets de otros clientes.',
    criterio: null,
  },
]

// Solo en los documentos subidos: el mismo documento da otro plazo para los urgentes (§5.2 contra §2.3)
const UPLOADED_EXTRA = {
  fuente: 'pág. 7 · §5.2', severidad: 'media',
  titulo: 'Un ticket urgente se responde en menos de 4 horas',
  descripcion: 'Los tickets urgentes reciben la primera respuesta en un plazo máximo de 4 horas hábiles.',
  criterio: null,
}
const UPLOADED_CONTRADICTION = { a: 1, b: 3, motivo: '§2.3 pide responder un ticket urgente en menos de 1 hora y §5.2 da hasta 4 horas' }

const q = (text: string) => JSON.stringify(text)

/** Un texto = error (el handler responde 422 con ese mensaje). Mismo TOML que arma el backend. */
export function importDocument(body: ImportRulesRequest): ImportedRules | string {
  const source = body.path ?? body.filename ?? ''
  if (!/\.(pdf|docx|md|markdown|txt)$/i.test(source)) return 'Usa un PDF, Word (.docx), Markdown (.md) o texto (.txt)'
  const m = body.url ? REPO_URL.exec(body.url.trim()) : null
  const project = m ? `${m[1]}/${m[2]}` : body.project_id ? getRepo(body.project_id).name : 'Mi proyecto'
  const name = source.split('/').pop()
  const lines = [
    `# reglas_negocio.toml — reglas de negocio de ${project} (formato: docs/PROPUESTA_REGLAS_NEGOCIO.md)`,
    `# Generado por IA voy desde «${name}». Revisa cada regla antes de usarlo:`,
    '# la IA puede equivocarse. Para verificar una regla, escribe una prueba test_rn001_… (o @pytest.mark.regla("RN-001")).',
    '',
    '[proyecto]',
    `nombre = ${q(project)}`,
    'formato = 2',
  ]
  const rules = body.filename ? [...IMPORTED_RULES, UPLOADED_EXTRA] : IMPORTED_RULES
  const pair = body.filename ? UPLOADED_CONTRADICTION : null
  const rid = (i: number) => `RN-${String(i + 1).padStart(3, '0')}`
  rules.forEach((r, i) => {
    lines.push('', `# Fuente: ${r.fuente}`)
    if (pair && (i === pair.a || i === pair.b)) lines.push(`# CONTRADICCIÓN ${rid(pair.a)} ${rid(pair.b)}: ${pair.motivo}`)
    lines.push('[[regla]]', `id          = ${q(rid(i))}`)
    lines.push(`titulo      = ${q(r.titulo)}`, `descripcion = ${q(r.descripcion)}`, `severidad   = ${q(r.severidad)}`)
    // Formato v2: todo entra en borrador, con su fuente y sus dudas (la regla sin criterio no sabe un dato)
    lines.push('estado      = "borrador"', `fuente      = ${q(r.fuente)}`)
    lines.push(`dudas       = [${r.criterio ? '' : q('¿Qué dato exacto se debe comprobar? El documento no lo dice')}]`)
    if (r.criterio) {
      const [given, when, then] = r.criterio.replace(/^Dado /, '').split(/, cuando |, entonces /)
      lines.push('', '  [[regla.escenario]]', `  dado     = ${q(given)}`, `  cuando   = ${q(when ?? '')}`, `  entonces = ${q(then ?? '')}`)
    }
  })
  const content = lines.join('\n') + '\n'
  return {
    content, count: rules.length, source, model: 'Gemini 3.5 Flash Lite',
    contradictions: pair ? [`${rid(pair.a)} (${rules[pair.a].fuente}) y ${rid(pair.b)} (${rules[pair.b].fuente}): ${pair.motivo}`] : [],
    doubts: ['§2.3 dice "urgente" pero no explica quién marca un ticket como urgente', '§4 menciona "horario de atención" sin decir cuál es'],
    validation: validate(content),
  }
}

/** Reglas mandadas con /api/analyze: un texto = no son válidas (422); si el repo ya es proyecto, se guardan en él. */
export function fromAnalyze(url: string, content: string): string | null {
  const check = validate(content)
  if (!check.valid) return check.error ?? 'Reglas no válidas'
  const project = findRepoByName(url.replace(/^https?:\/\/[^/]+\//, '').replace(/\.git$/, ''))
  if (project) uploads.set(project.id, { content, updated_at: new Date().toISOString() })
  return null
}

// ─── Aprobación (POST …/reglas/estado y PUT …/reglas/{id}/dudas) ───

/** Cambia (o agrega) un campo de la regla `id` en el texto cargado en la app, antes de sus escenarios. */
function setField(text: string, id: string, key: string, line: string): string {
  const lines = text.split('\n')
  const at = lines.findIndex((l) => new RegExp(`^\\s*id\\s*=\\s*"${id}"`).test(l))
  let end = at + 1
  while (end < lines.length && !/^\s*\[\[/.test(lines[end])) end++
  const field = new RegExp(`^\\s*${key}\\s*=`)
  const existing = lines.slice(at, end).findIndex((l) => field.test(l))
  if (existing >= 0) lines[at + existing] = line
  else lines.splice(at + 1, 0, line)
  return lines.join('\n')
}

const REPO_COPY_NOTE =
  'Guardado en la copia del proyecto, no en GitHub: descarga el archivo (Descargar para el repo) y haz commit. Un análisis nuevo vuelve a clonar el repositorio y su archivo manda otra vez'

/** Un texto = error (el handler responde 409/404 con ese mensaje). Las del repo se guardan en su copia de trabajo. */
function editable(repoId: string): { text: string; rules: ParsedRule[]; save: (text: string) => void; inRepo: boolean } | string {
  getRepo(repoId)
  const own = REPO_RULES[repoId]
  if (own) {
    if (!validate(own).valid) return `El ${FILENAME} del repositorio tiene errores: corrígelo primero`
    return { text: own, rules: parse(own).rules, save: (text) => void (REPO_RULES[repoId] = text), inRepo: true }
  }
  const up = uploads.get(repoId)
  if (!up) return 'El proyecto no tiene reglas cargadas en la app'
  return { text: up.content, rules: parse(up.content).rules, save: (text) => void uploads.set(repoId, { content: text, updated_at: new Date().toISOString() }), inRepo: false }
}

export function setStates(repoId: string, ids: string[], status: RuleApproval): ProjectRules | string {
  const cur = editable(repoId)
  if (typeof cur === 'string') return cur
  let text = cur.text
  const messages: string[] = []
  let changed = false
  for (const id of new Set(ids)) {
    const rule = cur.rules.find((r) => r.id === id)
    if (!rule) return `${id} no está en las reglas del proyecto`
    if (rule.status === status) continue
    if (status === 'aprobada' && (rule.doubts ?? []).length) {
      messages.push(`${id}: tiene ${rule.doubts!.length} duda(s) abierta(s); resuélvelas antes de aprobarla`)
      continue
    }
    text = setField(text, id, 'estado', `estado      = ${q(status)}`)
    changed = true
  }
  if (changed) {
    cur.save(text)
    if (cur.inRepo) messages.push(REPO_COPY_NOTE)
  }
  return { ...projectRules(repoId), messages }
}

export function setDoubts(repoId: string, ruleId: string, doubts: string[]): ProjectRules | string {
  const cur = editable(repoId)
  if (typeof cur === 'string') return cur
  if (!cur.rules.some((r) => r.id === ruleId)) return `${ruleId} no está en las reglas del proyecto`
  const text = setField(cur.text, ruleId, 'dudas', `dudas       = [${doubts.map(q).join(', ')}]`)
  cur.save(text)
  return { ...projectRules(repoId), messages: cur.inRepo ? [REPO_COPY_NOTE] : [] }
}
