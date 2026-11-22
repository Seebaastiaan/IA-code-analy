import type { RulePreview } from '../types'

export const FLOW_STEPS = [
  { title: 'Importar', text: 'Sube el documento de requisitos y la IA saca las reglas.' },
  { title: 'Preguntas y aprobación', text: 'Contesta Sí o No a lo ambiguo y aprueba las reglas. Solo lo aprobado se verifica.' },
  { title: 'Preparar todo', text: 'El programa prepara el entorno, escribe las pruebas y las corre.' },
  { title: 'Resultado', text: 'Analiza el repositorio y mira qué reglas se cumplen.' },
] as const

const isDraft = (r: RulePreview) => (r.status ?? 'aprobada') === 'borrador'

/** Paso en el que está el proyecto según sus reglas: sin reglas → 0; con borradores → 1; todo aprobado → 2. */
export function currentStep(rules: RulePreview[]): number {
  if (!rules.length) return 0
  return rules.some(isDraft) ? 1 : 2
}

/** Lo que el programa recomienda hacer ahora, en una frase y con el paso al que lleva. */
export function nextAction(rules: RulePreview[]): { text: string; step: number; label: string } {
  if (!rules.length) return { text: 'Empieza importando el documento de requisitos del proyecto.', step: 0, label: 'Importar' }
  const drafts = rules.filter(isDraft)
  if (drafts.length) {
    const asking = drafts.filter((r) => (r.doubts ?? []).length > 0).length
    const text =
      asking > 0
        ? `Tienes ${asking} regla${asking === 1 ? '' : 's'} con preguntas por contestar y ${drafts.length} en borrador.`
        : `Tienes ${drafts.length} regla${drafts.length === 1 ? '' : 's'} en borrador por aprobar.`
    return { text, step: 1, label: 'Revisar las reglas' }
  }
  return { text: 'Todas las reglas están aprobadas: ya puedes pulsar «Preparar todo».', step: 2, label: 'Ir a «Preparar todo»' }
}

export interface Question {
  rule: RulePreview
  doubt: string
}

/** Las dudas de todas las reglas que siguen en borrador, en una sola lista. */
export function pendingQuestions(rules: RulePreview[]): Question[] {
  return rules
    .filter((r) => (r.status ?? 'aprobada') === 'borrador')
    .flatMap((rule) => (rule.doubts ?? []).map((doubt) => ({ rule, doubt })))
}
