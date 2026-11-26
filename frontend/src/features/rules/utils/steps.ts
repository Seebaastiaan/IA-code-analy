import type { RulePreview } from '../types'

export const FLOW_STEPS = [
  { title: 'Importar', text: 'Al analizar, el programa saca las reglas del documento de requisitos del repo.' },
  { title: 'Preguntas y aprobación', text: 'Contesta Sí o No a lo ambiguo y aprueba las reglas. Solo lo aprobado se verifica.' },
  { title: 'Preparar todo', text: 'El programa prepara el entorno, escribe las pruebas y las corre.' },
  { title: 'Resultado', text: 'Analiza el repositorio y mira qué reglas se cumplen.' },
] as const

const isDraft = (r: RulePreview) => (r.status ?? 'aprobada') === 'borrador'

const hasDoubts = (r: RulePreview) => (r.doubts ?? []).length > 0

/**
 * Paso en el que está el proyecto según sus reglas: sin reglas → 0; con preguntas por contestar → 1; si no, → 2
 * («Preparar todo» aprueba solo los borradores sin dudas: no hace falta aprobarlos a mano antes).
 */
export function currentStep(rules: RulePreview[]): number {
  if (!rules.length) return 0
  return rules.some((r) => isDraft(r) && hasDoubts(r)) ? 1 : 2
}

/** Lo que el programa recomienda hacer ahora, en una frase y con el paso al que lleva. */
export function nextAction(rules: RulePreview[], contradictions = 0): { text: string; step: number; label: string } {
  if (contradictions > 0)
    return {
      text: `El documento se contradice en ${contradictions === 1 ? 'un punto' : `${contradictions} puntos`}: elige cuál regla vale.`,
      step: 0,
      label: 'Decidir',
    }
  if (!rules.length) return { text: 'Empieza importando el documento de requisitos del proyecto.', step: 0, label: 'Importar' }
  const drafts = rules.filter(isDraft)
  const asking = drafts.filter(hasDoubts).length
  if (asking > 0)
    return { text: `Tienes ${asking} regla${asking === 1 ? '' : 's'} con preguntas por contestar.`, step: 1, label: 'Contestar' }
  if (drafts.length)
    return {
      text: `Pulsa «Preparar todo»: aprueba ${drafts.length === 1 ? 'la regla en borrador' : `las ${drafts.length} reglas en borrador`} y las comprueba.`,
      step: 2,
      label: 'Ir a «Preparar todo»',
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
