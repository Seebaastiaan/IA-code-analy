import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useRef, useState } from 'react'
import { harnessQuery, projectRulesQuery, ruleTestsQuery, rulesApi } from '../api/rules.api'

/** Los pasos técnicos que el programa hace solo (docs/PLAN_REGLAS_AUTOMATICO.md, pasos 1 y 2). */
export const AUTO_STEPS = [
  { id: 'reglas', label: 'Aprobar las reglas que no tienen dudas' },
  { id: 'arnes', label: 'Preparar el entorno de pruebas del proyecto' },
  { id: 'humo', label: 'Comprobar que el proyecto arranca' },
  { id: 'pruebas', label: 'Escribir una prueba para cada regla' },
  { id: 'correr', label: 'Ejecutar las pruebas' },
  { id: 'fuerza', label: 'Verificar que las pruebas sí detectan una regla rota' },
  { id: 'revision', label: 'Segunda opinión: la IA lee el código por su cuenta y se compara' },
] as const

export type AutoStepId = (typeof AUTO_STEPS)[number]['id']
export type AutoStatus = 'pendiente' | 'haciendo' | 'hecho' | 'fallo'
export interface AutoStep {
  id: AutoStepId
  label: string
  status: AutoStatus
  /** Lo que pasó, en una frase (qué se hizo o por qué se detuvo y cómo resolverlo) */
  note: string | null
}

const POLL_MS = 2000
// Un paso lento (instalar dependencias, correr pruebas) no debe colgar el botón para siempre
const MAX_WAIT_MS = 15 * 60_000

const initial = (): AutoStep[] => AUTO_STEPS.map((s) => ({ ...s, status: 'pendiente', note: null }))

/** El flujo se detiene a propósito (un paso no pudo seguir o la persona pulsó Detener). */
class Stop extends Error {}

const STOPPED = 'Detenido'

/**
 * «Preparar todo»: encadena lo que antes eran seis botones (aprobar reglas, arnés, prueba de humo, pruebas,
 * corrida y prueba de fuerza) con los endpoints de siempre, y se detiene en el primer problema diciendo qué hacer.
 * Aprueba por el equipo el arnés y las pruebas que pasan y son fuertes; el resto queda para revisar.
 */
export function useAutoVerify(repoId: string) {
  const queryClient = useQueryClient()
  const [steps, setSteps] = useState<AutoStep[]>(initial)
  const [running, setRunning] = useState(false)
  const [summary, setSummary] = useState<string | null>(null)
  const cancelled = useRef(false)

  const patch = useCallback(
    (id: AutoStepId, status: AutoStatus, note: string | null = null) => setSteps((all) => all.map((s) => (s.id === id ? { ...s, status, note } : s))),
    [],
  )

  const run = useCallback(async () => {
    cancelled.current = false
    setRunning(true)
    setSummary(null)
    setSteps(initial())
    const fail = (id: AutoStepId, note: string): never => {
      patch(id, 'fallo', note)
      throw new Stop(note)
    }
    const check = () => {
      if (cancelled.current) throw new Stop(STOPPED)
    }
    // Espera a que termine un trabajo en segundo plano del servidor, consultando cada 2 s
    const until = async <T,>(read: () => Promise<T>, done: (v: T) => boolean): Promise<T> => {
      const started = Date.now()
      for (;;) {
        check()
        const value = await read()
        if (done(value)) return value
        if (Date.now() - started > MAX_WAIT_MS) throw new Stop('Tardó demasiado: inténtalo de nuevo')
        await new Promise((r) => setTimeout(r, POLL_MS))
      }
    }
    const tests = async () => {
      const view = await rulesApi.tests(repoId)
      queryClient.setQueryData(ruleTestsQuery(repoId).queryKey, view)
      return view
    }
    const harness = async () => {
      const view = await rulesApi.harness(repoId)
      queryClient.setQueryData(harnessQuery(repoId).queryKey, view)
      return view
    }

    try {
      // 1 · Reglas: las que no tienen dudas se aprueban solas (las demás esperan una decisión del equipo)
      patch('reglas', 'haciendo')
      let project = await rulesApi.project(repoId)
      const source = project.active === 'repo' ? project.repo : project.uploaded
      const rules = source?.valid ? source.rules : []
      if (!rules.length) fail('reglas', 'Todavía no hay reglas: sube el documento de requisitos o escribe una regla.')
      const ready = rules.filter((r) => (r.status ?? 'aprobada') === 'borrador' && !(r.doubts ?? []).length).map((r) => r.id)
      if (ready.length) project = await rulesApi.setStates(repoId, ready, 'aprobada', 'programa')
      queryClient.setQueryData(projectRulesQuery(repoId).queryKey, project)
      const current = project.active === 'repo' ? project.repo : project.uploaded
      const all = current?.rules ?? []
      const approved = all.filter((r) => (r.status ?? 'aprobada') === 'aprobada')
      if (!approved.length) fail('reglas', 'Todas las reglas tienen dudas: respóndelas y vuelve a intentar.')
      const waiting = all.length - approved.length
      patch('reglas', 'hecho', waiting ? `${approved.length} aprobadas · ${waiting} esperan tu decisión (tienen dudas)` : `${approved.length} aprobadas`)
      check()

      // 2 · Entorno de pruebas (arnés): el del repo si ya existe; si no, la IA lo propone
      patch('arnes', 'haciendo')
      let view = await harness()
      if (!view.cloned) fail('arnes', 'Analiza el repositorio una vez para poder preparar sus pruebas.')
      if (!view.harness) {
        if (view.repo_harness) view = await rulesApi.harnessFromRepo(repoId)
        else if (view.can_generate) view = await rulesApi.proposeHarness(repoId)
        else fail('arnes', 'No se pudo preparar: falta configurar la clave de la IA o el repositorio no usa FastAPI, Flask ni Django.')
        queryClient.setQueryData(harnessQuery(repoId).queryKey, view)
      }
      patch('arnes', 'hecho', view.harness?.origin === 'repo' ? 'Usé el conftest.py de tu repositorio' : 'La IA lo preparó con el mapa de tu proyecto')
      check()

      // 3 · Prueba de humo y aprobación del entorno
      patch('humo', 'haciendo')
      if (!view.sandbox) fail('humo', 'Falta el sandbox: configura SANDBOX=docker o wsl para poder correr pruebas.')
      if (view.harness?.smoke !== 'paso') {
        await rulesApi.runSmoke(repoId)
        view = await until(harness, (v) => v.harness?.smoke !== 'corriendo')
      }
      if (view.harness?.smoke !== 'paso') fail('humo', view.harness?.smoke_message ?? 'El entorno no arrancó: revisa el arnés en «Avanzado».')
      if (!view.harness?.approved) await rulesApi.approveHarness(repoId)
      await harness()
      patch('humo', 'hecho', 'El entorno arranca y se aprobó')
      check()

      // 4 · Una prueba por regla aprobada
      patch('pruebas', 'haciendo')
      await rulesApi.generateTests(repoId)
      let t = await until(tests, (v) => !v.busy)
      const written = t.rules.filter((r) => r.test).length
      if (!written) fail('pruebas', t.messages[0] ?? 'La IA no pudo escribir pruebas: reintenta en unos minutos.')
      patch('pruebas', 'hecho', `${written} pruebas escritas${t.messages.length ? ` · ${t.messages[0]}` : ''}`)
      check()

      // 5 · Corrida en el sandbox
      patch('correr', 'haciendo')
      await rulesApi.runTests(repoId)
      t = await until(tests, (v) => !v.busy)
      const verdicts = t.rules.map((r) => r.test?.run?.verdict).filter(Boolean)
      const count = (v: string) => verdicts.filter((x) => x === v).length
      patch('correr', 'hecho', `${count('cumple')} cumplen · ${count('no_cumple')} no cumplen · ${count('prueba_rota')} con prueba rota`)
      check()

      // 6 · Prueba de fuerza: ¿la prueba detecta una violación de la regla?
      patch('fuerza', 'haciendo')
      await rulesApi.strengthTests(repoId)
      t = await until(tests, (v) => !v.busy)
      const weak = t.rules.filter((r) => r.test?.strength && r.test.strength.status !== 'fuerte' && r.test.strength.status !== 'no_aplica').length
      patch('fuerza', 'hecho', weak ? `${weak} pruebas flojas para revisar` : 'Todas detectan las violaciones')
      check()

      // 7 · Segunda opinión: la IA lee el código sin ver la prueba y se compara con el resultado de la corrida
      patch('revision', 'haciendo')
      let read = 0
      if (t.can_explain) {
        for (const row of t.rules) {
          check()
          const verdict = row.test?.run?.verdict
          if (row.test && (verdict === 'cumple' || verdict === 'no_cumple') && (!row.evidence || row.evidence.stale)) {
            t = await rulesApi.explainRule(repoId, row.id)
            read++
          }
        }
        t = await tests()
      }
      const different = t.rules.filter((r) => r.crosscheck.status === 'discrepa').length
      // Se aprueban solas las pruebas que pasan, son fuertes y coinciden con la lectura del código
      const trusted = t.rules.filter((r) => r.test && !r.test.approved && !r.test.blocked && r.test.strength?.status === 'fuerte' && r.crosscheck.status === 'coincide').map((r) => r.id)
      if (trusted.length) {
        t = await rulesApi.approveTests(repoId, trusted)
        queryClient.setQueryData(ruleTestsQuery(repoId).queryKey, t)
      }
      const unread = !t.can_explain ? ' · sin IA para leer el código: nada se aprueba solo' : ''
      patch('revision', 'hecho', `${trusted.length} pruebas aprobadas por el programa${different ? ` · ${different} no coinciden con la lectura del código: revísalas` : ''}${read ? '' : ' · sin lecturas nuevas'}${unread}`)
      setSummary('Listo. El siguiente análisis usará estas reglas y pruebas.')
      void queryClient.invalidateQueries({ queryKey: ['rules', repoId] })
    } catch (e) {
      if (e instanceof Stop) {
        if (e.message === STOPPED) setSteps((all) => all.map((s) => (s.status === 'haciendo' ? { ...s, status: 'pendiente', note: STOPPED } : s)))
      } else {
        // Un error del servidor (409, 422, 503…) llega con su mensaje: se muestra en el paso que estaba corriendo
        const message = e instanceof Error ? e.message : 'Algo falló'
        setSteps((all) => all.map((s) => (s.status === 'haciendo' ? { ...s, status: 'fallo', note: message } : s)))
      }
    } finally {
      setRunning(false)
    }
  }, [repoId, queryClient, patch])

  const stop = useCallback(() => {
    cancelled.current = true
  }, [])

  return { steps, running, summary, run, stop }
}
