import type { CHIP_TONES } from '@/shared/ui/styles'
import type { BusinessRuleResult, RuleLevel, RulesPrecheck, RuleStatus, RulesValidation, TestOutcome } from '../types'

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
      : { tone: 'neutral', uses: null, title: 'Este repo no declara reglas de negocio', detail: 'Descarga la plantilla o escríbelas aquí; si no, el análisis no verifica reglas.' }
  return { tone: 'neutral', uses: app ? 'app' : null, title: 'No se pudieron revisar las reglas', detail: p.message }
}
