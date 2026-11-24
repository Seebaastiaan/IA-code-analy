import type { RuleTestRow, RuleTestsView } from '../types'

/**
 * Las pruebas que «Preparar todo» no aprobó solo y esperan a una persona (como app.projects.preparar.trusted_by_program,
 * al revés): qué dice cada una, por qué no se aprobó sola y qué conviene hacer, en pocas palabras.
 */
export interface ReviewItem {
  row: RuleTestRow
  /** true = la prueba dice que se cumple */
  passes: boolean
  /** Por qué no se aprobó sola (una frase por control que no pasó) */
  why: string[]
  /** Qué conviene hacer, en una frase */
  advice: string
  /** Si conviene aprobarla tal como está */
  recommended: boolean
  /** El primer fallo de la prueba (solo si no se cumple) */
  failure: string | null
}

const MAX_FAILURE = 200

const waiting = (r: RuleTestRow) =>
  r.test?.kind === 'prueba' && !r.test.approved && (r.test.run?.verdict === 'cumple' || r.test.run?.verdict === 'no_cumple')

export function reviewItems(view: RuleTestsView | undefined): ReviewItem[] {
  return (view?.rules ?? []).filter(waiting).map((row) => {
    const test = row.test!
    const passes = test.run!.verdict === 'cumple'
    const why: string[] = []
    const s = test.strength
    let weak = false
    if (passes && s?.status !== 'fuerte') {
      weak = s?.status === 'parcial' || s?.status === 'debil'
      why.push(weak && s ? `Siguió pasando con ${s.total - s.killed} de ${s.total} cambios al código: puede que no compruebe la regla` : 'No se pudo medir si detecta fallos')
    }
    if (row.crosscheck.status === 'discrepa') why.push(passes ? 'La IA leyó el código y cree que la regla no está completa' : 'La IA leyó el código y cree que la regla sí está')
    if (row.crosscheck.status === 'sin_revisar') why.push('Falta la segunda opinión (la IA no respondió)')
    // Como trusted_by_program: el repo trae sus propias pruebas de la regla y el análisis también las corre
    const ownTests = !passes && row.repo_tests > 0
    if (ownTests) why.push(`El repositorio trae ${row.repo_tests === 1 ? 'su propia prueba' : `${row.repo_tests} pruebas propias`} de esta regla: compara con su resultado en el análisis`)
    const disagree = row.crosscheck.status === 'discrepa'
    const advice = weak
      ? 'Mejor no la apruebes todavía: «Volver a preparar» la escribe de nuevo con lo que no notó.'
      : disagree && passes
        ? 'Revisa el código de la regla antes de aprobar: si está completo, apruébala.'
        : disagree
          ? 'Lee el fallo: si es lo que pide el documento, apruébala; si la prueba se equivocó, no.'
          : row.crosscheck.status === 'sin_revisar'
            ? '«Volver a preparar» pide la segunda opinión otra vez; o apruébala si el resultado te parece correcto.'
            : 'Si el resultado te parece correcto, apruébala.'
    const failed = passes ? null : (test.run!.tests.find((t) => t.outcome === 'failed' && t.message)?.message ?? null)
    return {
      row,
      passes,
      why,
      advice,
      recommended: !weak && !disagree && !ownTests,
      failure: failed && failed.length > MAX_FAILURE ? `${failed.slice(0, MAX_FAILURE)}…` : failed,
    }
  })
}

/** Pruebas que no pudieron preparar su caso: no hay nada que decidir, «Volver a preparar» las escribe de nuevo. */
export const brokenCount = (view: RuleTestsView | undefined) =>
  (view?.rules ?? []).filter((r) => r.test?.kind === 'prueba' && !r.test.approved && r.test.run?.verdict === 'prueba_rota').length
