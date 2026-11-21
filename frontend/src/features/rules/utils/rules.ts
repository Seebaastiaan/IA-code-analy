import type { CHIP_TONES } from '@/shared/ui/styles'
import type { BusinessRuleResult, Harness, HarnessOrigin, MapSummary, RuleLevel, RulesPrecheck, RuleStatus, RulesValidation, SmokeStatus, TestOutcome } from '../types'

type Tone = keyof typeof CHIP_TONES

export const STATUS: Record<RuleStatus, { label: string; tone: Tone; order: number }> = {
  no_cumple: { label: 'No cumple', tone: 'danger', order: 0 },
  sin_verificar: { label: 'Sin verificar', tone: 'neutral', order: 1 },
  cumple: { label: 'Cumple', tone: 'success', order: 2 },
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
  error: { label: 'Error', tone: 'danger' },
  skipped: { label: 'Omitida', tone: 'neutral' },
  not_run: { label: 'No corrió', tone: 'neutral' },
  sin_ejecutar: { label: 'Sin ejecutar', tone: 'neutral' },
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

/** Extensiones que la IA puede leer (backend/app/projects/reglas_importar.py) */
export const DOCUMENT_EXTENSIONS = ['.pdf', '.docx', '.md', '.markdown', '.txt']
export const MAX_DOCUMENT_BYTES = 10 * 1024 * 1024

/** PDF, Word o Markdown: se importa con IA. Un .toml (o cualquier otro) se carga tal cual en el editor. */
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
