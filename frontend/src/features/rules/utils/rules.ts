import type { CHIP_TONES } from '@/shared/ui/styles'
import type {
  BusinessRuleResult, Crosscheck, Harness, HarnessOrigin, MapSummary, MatrixCell, PermissionMatrix, RuleLevel, RulesPrecheck, RuleStatus, RuleTestState,
  RuleTestsView, RulesValidation, RuleTestRun, SmokeStatus, StrengthStatus, SupportEvidence, TestOutcome,
} from '../types'

// (resultado de la prueba, lectura del código) → ¿coinciden? Igual que `crosscheck` del backend (app/projects/pruebas.py)
const CROSS: Record<string, [Crosscheck['status'], string]> = {
  'cumple|implementada': ['coincide', 'La prueba pasa y la lectura del código confirma que la regla está implementada.'],
  'no_cumple|no_encontrada': ['coincide', 'La prueba falla y la lectura no encuentra la regla en el código: probablemente no está implementada.'],
  'no_cumple|parcial': ['coincide', 'La prueba falla y la lectura ve la regla solo en parte: falta cubrir algo.'],
  'cumple|parcial': ['discrepa', 'La prueba pasa, pero la lectura del código dice que la regla solo se cumple en parte: la prueba puede ser floja.'],
  'cumple|no_encontrada': ['discrepa', 'La prueba pasa, pero no se encontró dónde el código implementa la regla: la prueba puede no comprobar lo que dice.'],
  'no_cumple|implementada': ['discrepa', 'La prueba falla, pero el código parece implementar la regla: la prueba puede estar mal escrita.'],
}

/** Contrasta el resultado de la prueba con la lectura independiente del código. */
export function crosscheck(run: Pick<RuleTestRun, 'verdict'> | null, evidence: Pick<SupportEvidence, 'verdict' | 'stale'> | null): Crosscheck {
  if (!run || (run.verdict !== 'cumple' && run.verdict !== 'no_cumple')) return { status: 'sin_revisar', note: 'Falta una prueba que corra y dé un resultado claro.' }
  if (!evidence || evidence.stale) return { status: 'sin_revisar', note: 'Falta leer el código de forma independiente (o la lectura es de una versión anterior).' }
  const [status, note] = CROSS[`${run.verdict}|${evidence.verdict}`]
  return { status, note }
}

type Tone = keyof typeof CHIP_TONES

export const STATUS: Record<RuleStatus, { label: string; tone: Tone; order: number }> = {
  no_cumple: { label: 'No cumple', tone: 'danger', order: 0 },
  no_implementada: { label: 'No implementada', tone: 'danger', order: 1 },
  prueba_rota: { label: 'Prueba rota', tone: 'brand', order: 2 },
  sin_verificar: { label: 'Sin verificar', tone: 'neutral', order: 3 },
  cumple: { label: 'Cumple', tone: 'success', order: 4 },
  fuera_del_codigo: { label: 'Fuera del código', tone: 'neutral', order: 5 },
}

export const LEVEL: Record<RuleLevel, string> = {
  pruebas: 'Pruebas',
  patron: 'Patrón',
  pruebas_y_patron: 'Pruebas y patrón',
  ninguno: 'Sin verificación',
}

export const OUTCOME: Record<TestOutcome, { label: string; tone: Tone }> = {
  passed: { label: 'Pasa', tone: 'success' },
  failed: { label: 'Falla', tone: 'danger' },
  broken: { label: 'Rota', tone: 'brand' },
  error: { label: 'Error', tone: 'danger' },
  skipped: { label: 'Omitida', tone: 'neutral' },
  not_run: { label: 'No corrió', tone: 'neutral' },
  sin_ejecutar: { label: 'Sin ejecutar', tone: 'neutral' },
}

/** Semáforo en lenguaje normal (docs/PLAN_REGLAS_AUTOMATICO.md, paso 5): verde se cumple, rojo no, amarillo necesita una decisión. */
export type Light = 'verde' | 'rojo' | 'amarillo' | 'gris'

export const LIGHT: Record<Light, { dot: string; label: string }> = {
  verde: { dot: '🟢', label: 'Se cumple' },
  rojo: { dot: '🔴', label: 'No se cumple' },
  amarillo: { dot: '🟡', label: 'Necesita una decisión' },
  gris: { dot: '⚪', label: 'Fuera del código' },
}

/** El color de un estado (el mismo que usa `plain`). */
export const lightOf = (status: RuleStatus): Light =>
  status === 'cumple' ? 'verde' : status === 'no_cumple' || status === 'no_implementada' ? 'rojo' : status === 'fuera_del_codigo' ? 'gris' : 'amarillo'

/** El resultado de una regla en una frase: qué pasó y con qué se comprobó, o qué caso falla y dónde. */
export function plain(r: BusinessRuleResult): { light: Light; text: string } {
  const failing = r.tests.find((t) => t.outcome === 'failed' || t.outcome === 'error')
  const passing = r.tests.filter((t) => t.outcome === 'passed').length
  switch (r.status) {
    case 'cumple':
      return { light: 'verde', text: passing ? `Se comprobó con ${passing} prueba${passing === 1 ? '' : 's'} que pasa${passing === 1 ? '' : 'n'}.` : 'Se comprobó buscando en el código: no aparece nada que la contradiga.' }
    case 'no_cumple':
      if (failing) return { light: 'rojo', text: `Falla el caso «${testFunction(failing.name)}» (${failing.file}:${failing.line}).${failing.message ? ` ${failing.message}` : ''}` }
      return { light: 'rojo', text: r.evidence[0] ? `El código hace algo que la regla prohíbe (${r.evidence[0].file}:${r.evidence[0].line}).` : 'El código no la cumple.' }
    case 'no_implementada':
      return { light: 'rojo', text: 'No encontré en el código nada que la implemente.' }
    case 'prueba_rota':
      return { light: 'amarillo', text: 'La prueba de esta regla no pudo correr: hay que revisarla o regenerarla.' }
    case 'sin_verificar':
      return { light: 'amarillo', text: 'Todavía no hay forma de comprobarla: falta aprobarla, una prueba o resolver sus dudas.' }
    default:
      return { light: 'gris', text: 'La hace una persona, no el sistema: no se comprueba con código.' }
  }
}

/** «34 de 40 reglas se cumplen · 2 no se cumplen · 4 necesitan una decisión» */
export function plainSummary(rules: BusinessRuleResult[]): string {
  const n = (l: Light) => rules.filter((r) => plain(r).light === l).length
  const outside = n('gris')
  const parts = [`${n('verde')} de ${rules.length - outside} reglas se cumplen`, n('rojo') && `${n('rojo')} no se cumple${n('rojo') === 1 ? '' : 'n'}`, n('amarillo') && `${n('amarillo')} necesita${n('amarillo') === 1 ? '' : 'n'} una decisión`]
  return parts.filter(Boolean).join(' · ')
}

/** Cuántas reglas conocidas acertó el programa, con una frase («acertó 11 de 12 reglas que conocían»). */
export const concordanceText = (known: number, hits: number, misses: number, unverified: number): string => {
  if (!known) return 'Marca las reglas que conoces (se cumple o se viola) para medir al programa.'
  const decided = hits + misses
  const extra = unverified ? ` · ${unverified} sin resultado todavía` : ''
  return decided ? `Acertó ${hits} de ${decided} reglas que conocías${extra}.` : `Todavía no hay resultado para tus ${known} reglas${extra}.`
}

export type StatusFilter = RuleStatus | 'todas'

/** Reglas con ese estado; las que no cumplen primero y, dentro de cada estado, en el orden del archivo. */
export function filterRules(rules: BusinessRuleResult[], status: StatusFilter): BusinessRuleResult[] {
  return rules
    .map((r, i) => ({ r, i }))
    .filter(({ r }) => status === 'todas' || r.status === status)
    .sort((a, b) => STATUS[a.r.status].order - STATUS[b.r.status].order || a.i - b.i)
    .map(({ r }) => r)
}

/** "test_rn002_…": nombre alternativo al marcador para una regla. */
export const testName = (ruleId: string) => `test_${ruleId.replace('-', '').toLowerCase()}_…`

/** Archivo de pytest y nombre de la función de un nodeid (tests/test_x.py::TestA::test_b → test_b). */
export const testFunction = (nodeid: string) => nodeid.split('::').slice(1).join('::') || nodeid

/** Descarga un texto como archivo (el reglas_negocio.toml para subirlo al repositorio). */
export function saveText(name: string, text: string, type = 'application/toml') {
  const url = URL.createObjectURL(new Blob([text], { type: `${type};charset=utf-8` }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

// ─── Documentos de requisitos (importar con IA) ───

/** Extensiones que se pueden subir: solo PDF y Word (backend/app/projects/reglas_importar.py) */
export const DOCUMENT_EXTENSIONS = ['.pdf', '.docx']
export const MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
export const INVALID_DOCUMENT = 'Tipo de archivo no válido: sube un PDF o un Word (.docx)'
export const NO_AI_FOR_DOCUMENTS = 'Para leer documentos hace falta configurar la clave de la IA (Gemini)'

/** PDF o Word: la IA saca las reglas. Cualquier otro tipo (incluido un .toml) se rechaza. */
export const isDocument = (name: string) => DOCUMENT_EXTENSIONS.some((ext) => name.toLowerCase().endsWith(ext))

/** Nombre del archivo de una ruta (docs/Requerimientos.pdf → Requerimientos.pdf). */
export const baseName = (path: string) => path.split('/').pop() || path

/** Contenido de un archivo en base64 (sin el prefijo data:…), para mandarlo en JSON. */
export async function fileToBase64(file: Blob): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer())
  let binary = ''
  // Por bloques: String.fromCharCode con millones de argumentos desborda la pila
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  return btoa(binary)
}

/** "owner/repo" de una URL de GitHub (mismo criterio que el backend); null si no es de GitHub. */
export function githubRepo(url: string): string | null {
  const m = /^https:\/\/(?:www\.)?github\.com\/([A-Za-z0-9._-]+)\/([A-Za-z0-9._-]+?)(?:\.git)?\/?$/i.exec(url.trim())
  return m ? `${m[1]}/${m[2]}` : null
}

export type PrecheckTone = 'ok' | 'warn' | 'error' | 'neutral'

export interface PrecheckView {
  tone: PrecheckTone
  title: string
  detail: string | null
  /** Qué reglas usará el análisis: las del repo, las cargadas en la app, las escritas en el formulario o ninguna */
  uses: 'repo' | 'app' | 'form' | null
}

const count = (v: RulesValidation) => `${v.rules.length} regla(s) · ${v.project}`

/**
 * Lo que dice la revisión de reglas en Nuevo análisis. `form` = reglas escritas o corregidas en el modal
 * (ya validadas): se mandan con el análisis y se usan si el repo no tiene un archivo válido.
 */
export function precheckView(p: RulesPrecheck, form: RulesValidation | null): PrecheckView {
  const file = p.file
  if (p.status === 'valid' && file)
    return {
      tone: 'ok', uses: 'repo', title: `${count(file)} de negocio`,
      detail: form
        ? `Se usarán las de ${file.path}: el archivo válido del repositorio gana a las escritas aquí.`
        : `${file.path} del repositorio${file.warnings?.length ? ` · ${file.warnings.length} aviso(s)` : ''}`,
    }
  if (form)
    return {
      tone: 'ok', uses: 'form', title: `${count(form)} escritas aquí`,
      detail: p.status === 'invalid'
        ? `${file?.path} del repositorio tiene errores: este análisis usará estas reglas corregidas. Súbelas al repositorio.`
        : 'Se guardan en el proyecto. Descárgalas y súbelas al repositorio para que cuenten como entregable.',
    }
  const app = p.uploaded?.valid ? p.uploaded : null
  if (p.status === 'invalid' && file)
    return app
      ? { tone: 'warn', uses: 'app', title: `${file.path} no es válido`, detail: `Se usarán las reglas corregidas en la app (${count(app)}). Error del repositorio: ${file.error}` }
      : { tone: 'error', uses: null, title: `${file.path} no es válido`, detail: file.error }
  if (p.status === 'missing')
    return app
      ? { tone: 'neutral', uses: 'app', title: 'Este repo no declara reglas de negocio', detail: `Se usarán las cargadas en la app (${count(app)}).` }
      : {
          tone: 'neutral', uses: null, title: 'Este repo no declara reglas de negocio',
          detail: p.can_import && p.documents.length
            ? `Encontré ${p.documents.length === 1 ? p.documents[0] : `${p.documents.length} documentos de requisitos`} en el repositorio: la IA puede sacar las reglas de ahí para que las revises. También puedes descargar la plantilla o escribirlas aquí.`
            : 'Descarga la plantilla o escríbelas aquí; si no, el análisis no verifica reglas.',
        }
  return { tone: 'neutral', uses: app ? 'app' : null, title: 'No se pudieron revisar las reglas', detail: p.message }
}

// ─── Mapa y arnés ───

export const FRAMEWORK: Record<string, string> = { fastapi: 'FastAPI', flask: 'Flask', django: 'Django' }

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/** "16 endpoints, 9 modelos y 4 roles" */
export function mapSummary(m: MapSummary): string {
  const parts = [plural(m.endpoints, 'endpoint', 'endpoints'), plural(m.models, 'modelo', 'modelos'), plural(m.roles.length, 'rol', 'roles')]
  return `${parts.slice(0, -1).join(', ')} y ${parts.at(-1)}`
}

export const HARNESS_ORIGIN: Record<HarnessOrigin, string> = { ia: 'Propuesto por IA', repo: 'Del repositorio', manual: 'Editado a mano' }

/** Estado del arnés para mostrar: aprobado gana a la prueba de humo. */
export function harnessStatus(h: Harness): { label: string; tone: Tone } {
  if (h.approved) return { label: 'Aprobado', tone: 'success' }
  if (h.errors.length) return { label: 'Con errores', tone: 'danger' }
  const smoke: Record<SmokeStatus, { label: string; tone: Tone }> = {
    pendiente: { label: 'Sin probar', tone: 'neutral' },
    corriendo: { label: 'Probando…', tone: 'brand' },
    paso: { label: 'Prueba de humo pasó', tone: 'success' },
    fallo: { label: 'Prueba de humo falló', tone: 'danger' },
  }
  return smoke[h.smoke]
}

/** test_humo_como[cajero] → "como('cajero')"; test_humo_crear[crear_producto] → "crear_producto()" */
export function smokeLabel(name: string): string {
  const m = /^test_humo_(\w+?)(?:\[(.*)\])?$/.exec(name)
  if (!m) return name
  const [, kind, param] = m
  if (kind === 'como') return `como('${param}')`
  if (kind === 'crear') return `${param}()`
  if (kind === 'extras') return param ?? kind
  return kind
}

// ─── Pruebas generadas ───

export const RULE_TEST_STATE: Record<RuleTestState, { label: string; tone: Tone }> = {
  sin_prueba: { label: 'Sin prueba', tone: 'neutral' },
  borrador: { label: 'Borrador', tone: 'brand' },
  aprobada: { label: 'Aprobada', tone: 'success' },
  desactualizada: { label: 'Desactualizada', tone: 'danger' },
}

/** Cuántas hay en cada estado y cuáles se pueden correr o aprobar ya (los botones de la tarjeta). */
export function testsSummary(view: RuleTestsView) {
  const count = (state: RuleTestState) => view.rules.filter((r) => r.state === state).length
  return {
    approved: count('aprobada'),
    drafts: count('borrador'),
    missing: count('sin_prueba'),
    outdated: count('desactualizada'),
    runnable: view.rules.filter((r) => r.test?.kind === 'prueba' && !r.test.errors.length && !r.test.outdated && r.test.run_status === 'pendiente').length,
    approvable: view.rules.filter((r) => r.test && !r.test.approved && !r.test.blocked).map((r) => r.id),
    /** Pasan y todavía no tienen prueba de fuerza */
    measurable: view.rules.filter((r) => r.test && !r.test.strength_blocked && r.test.strength_status === 'pendiente').length,
    /** Con prueba de fuerza débil: pasan pero no verifican la regla */
    weak: view.rules.filter((r) => r.test?.strength?.status === 'debil').length,
  }
}

// ─── Fase 5: prueba de fuerza, evidencia y matriz de permisos ───

export const STRENGTH: Record<StrengthStatus, { label: string; tone: Tone }> = {
  fuerte: { label: 'Prueba fuerte', tone: 'success' },
  parcial: { label: 'Prueba parcial', tone: 'brand' },
  debil: { label: 'Prueba débil', tone: 'danger' },
  no_aplica: { label: 'Fuerza: no aplica', tone: 'neutral' },
}

export const EVIDENCE: Record<SupportEvidence['verdict'], { label: string; tone: Tone }> = {
  implementada: { label: 'Parece implementada', tone: 'success' },
  parcial: { label: 'Parcial', tone: 'brand' },
  no_encontrada: { label: 'No encontrada', tone: 'neutral' },
}

/** Siguiente valor de una celda al hacer clic: vacía → permitido → prohibido → vacía. */
export function nextCell(cell: MatrixCell | undefined): MatrixCell | undefined {
  return cell === undefined ? 'permitido' : cell === 'permitido' ? 'prohibido' : undefined
}

/** Lo que se manda al guardar: todas las acciones, con null en las celdas vacías (quedan fuera de la matriz). */
export function matrixPayload(matrix: PermissionMatrix): Record<string, Record<string, MatrixCell | null>> {
  return Object.fromEntries(matrix.actions.map((a) => [a.id, Object.fromEntries(matrix.roles.map((r) => [r, a.cells[r] ?? null]))]))
}

/** Celdas marcadas (las que entran a la prueba). */
export function markedCells(matrix: PermissionMatrix): number {
  return matrix.actions.reduce((n, a) => n + matrix.roles.filter((r) => a.cells[r]).length, 0)
}

/** Marca la matriz con lo que hace el código hoy (el equipo lo revisa: el oráculo es la regla, no el código). */
export function matrixFromCode(matrix: PermissionMatrix): PermissionMatrix {
  return {
    ...matrix,
    actions: matrix.actions.map((a) =>
      a.suggested.length ? { ...a, cells: Object.fromEntries(matrix.roles.map((r) => [r, a.suggested.includes(r) ? 'permitido' : 'prohibido'])) } : a,
    ),
  }
}
