import { rulesApi } from '@/features/rules/api/rules.api'
import type { PrepareStep, PrepareStepId, PrepareView } from '@/features/rules/types'

/**
 * «Preparar todo» del backend simulado (app.projects.preparar): encadena los mismos pasos llamando a las rutas
 * simuladas de siempre y guarda el avance por proyecto, como el servidor.
 */

const STEPS: [PrepareStepId, string][] = [
  ['reglas', 'Aprobar las reglas que no tienen dudas'],
  ['arnes', 'Preparar el entorno de pruebas del proyecto'],
  ['humo', 'Comprobar que el proyecto arranca'],
  ['pruebas', 'Escribir una prueba para cada regla'],
  ['correr', 'Ejecutar las pruebas'],
  ['fuerza', 'Verificar que las pruebas sí detectan una regla rota'],
  ['revision', 'Segunda opinión: la IA lee el código por su cuenta y se compara'],
]
const STOPPED = 'Detenido'
const POLL_MS = 500

interface Job extends PrepareView {
  cancelled: boolean
}

const jobs = new Map<string, Job>()

const fresh = (): PrepareStep[] => STEPS.map(([id, label]) => ({ id, label, status: 'pendiente', note: null }))
const out = (job: Job | undefined): PrepareView =>
  job
    ? { running: job.running, steps: job.steps.map((s) => ({ ...s })), summary: job.summary, started_at: job.started_at, finished_at: job.finished_at }
    : { running: false, steps: fresh(), summary: null, started_at: null, finished_at: null }

class Stop extends Error {}

async function flow(repoId: string, job: Job) {
  const patch = (id: PrepareStepId, status: PrepareStep['status'], note: string | null = null) => {
    job.steps = job.steps.map((s) => (s.id === id ? { ...s, status, note } : s))
  }
  const fail = (id: PrepareStepId, note: string): never => {
    patch(id, 'fallo', note)
    throw new Stop(note)
  }
  const check = () => {
    if (job.cancelled) throw new Stop(STOPPED)
  }
  const until = async <T,>(read: () => Promise<T>, done: (v: T) => boolean): Promise<T> => {
    for (;;) {
      check()
      const value = await read()
      if (done(value)) return value
      await new Promise((r) => setTimeout(r, POLL_MS))
    }
  }
  const tests = () => rulesApi.tests(repoId)
  const harness = () => rulesApi.harness(repoId)

  patch('reglas', 'haciendo')
  let project = await rulesApi.project(repoId)
  const source = project.active === 'repo' ? project.repo : project.uploaded
  const rules = source?.valid ? source.rules : []
  if (!rules.length) fail('reglas', 'Todavía no hay reglas: sube el documento de requisitos o escribe una regla.')
  const ready = rules.filter((r) => (r.status ?? 'aprobada') === 'borrador' && !(r.doubts ?? []).length).map((r) => r.id)
  if (ready.length) project = await rulesApi.setStates(repoId, ready, 'aprobada', 'programa')
  const current = project.active === 'repo' ? project.repo : project.uploaded
  const all = current?.rules ?? []
  const approved = all.filter((r) => (r.status ?? 'aprobada') === 'aprobada')
  if (!approved.length) fail('reglas', 'Todas las reglas tienen dudas: respóndelas y vuelve a intentar.')
  const waiting = all.length - approved.length
  patch('reglas', 'hecho', waiting ? `${approved.length} aprobadas · ${waiting} esperan tu decisión (tienen dudas)` : `${approved.length} aprobadas`)
  check()

  patch('arnes', 'haciendo')
  let view = await harness()
  if (!view.cloned) fail('arnes', 'Analiza el repositorio una vez para poder preparar sus pruebas.')
  if (!view.harness) {
    if (view.repo_harness) view = await rulesApi.harnessFromRepo(repoId)
    else if (view.can_generate) view = await rulesApi.proposeHarness(repoId)
    else fail('arnes', 'No se pudo preparar: falta configurar la clave de la IA o el repositorio no usa FastAPI, Flask ni Django.')
  }
  patch('arnes', 'hecho', view.harness?.origin === 'repo' ? 'Usé el conftest.py de tu repositorio' : 'La IA lo preparó con el mapa de tu proyecto')
  check()

  patch('humo', 'haciendo')
  if (!view.sandbox) fail('humo', 'Falta el sandbox: configura SANDBOX=docker o wsl para poder correr pruebas.')
  if (view.harness?.smoke !== 'paso') {
    await rulesApi.runSmoke(repoId)
    view = await until(harness, (v) => v.harness?.smoke !== 'corriendo')
  }
  if (view.harness?.smoke !== 'paso') fail('humo', view.harness?.smoke_message ?? 'El entorno no arrancó: revisa el arnés en «Avanzado».')
  if (!view.harness?.approved) await rulesApi.approveHarness(repoId)
  patch('humo', 'hecho', 'El entorno arranca y se aprobó')
  check()

  patch('pruebas', 'haciendo')
  let t = await tests()
  if (t.rules.some((r) => !r.test || r.test.outdated)) {
    await rulesApi.generateTests(repoId)
    t = await until(tests, (v) => !v.busy)
  }
  const written = t.rules.filter((r) => r.test).length
  if (!written) fail('pruebas', t.messages[0] ?? 'La IA no pudo escribir pruebas: reintenta en unos minutos.')
  patch('pruebas', 'hecho', `${written} pruebas escritas${t.messages.length ? ` · ${t.messages[0]}` : ''}`)
  check()

  patch('correr', 'haciendo')
  if (t.rules.some((r) => r.test?.kind === 'prueba' && !r.test.errors.length && !r.test.outdated && r.test.run_status === 'pendiente')) {
    await rulesApi.runTests(repoId)
    t = await until(tests, (v) => !v.busy)
  }
  const verdicts = t.rules.map((r) => r.test?.run?.verdict).filter(Boolean)
  const count = (v: string) => verdicts.filter((x) => x === v).length
  patch('correr', 'hecho', `${count('cumple')} cumplen · ${count('no_cumple')} no cumplen · ${count('prueba_rota')} con prueba rota`)
  check()

  patch('fuerza', 'haciendo')
  if (t.rules.some((r) => r.test && r.test.strength_status === 'pendiente' && !r.test.strength_blocked)) {
    await rulesApi.strengthTests(repoId)
    t = await until(tests, (v) => !v.busy)
  }
  const weak = t.rules.filter((r) => r.test?.strength && r.test.strength.status !== 'fuerte' && r.test.strength.status !== 'no_aplica').length
  patch('fuerza', 'hecho', weak ? `${weak} pruebas flojas para revisar` : 'Todas detectan las violaciones')
  check()

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
  // Como app.projects.preparar.trusted_by_program: pasa y es fuerte, o falla; y en los dos casos coincide con la lectura del código
  const trusted = t.rules
    .filter((r) => r.test && !r.test.approved && !r.test.blocked && r.crosscheck.status === 'coincide')
    .filter((r) => (r.test?.run?.verdict === 'cumple' && r.test.strength?.status === 'fuerte') || r.test?.run?.verdict === 'no_cumple')
    .map((r) => r.id)
  if (trusted.length) await rulesApi.approveTests(repoId, trusted)
  const pendingReview = t.rules.filter((r) => r.test?.kind === 'prueba' && !r.test.approved && !trusted.includes(r.id)).length
  const unread = !t.can_explain ? ' · sin IA para leer el código: nada se aprueba solo' : ''
  patch('revision', 'hecho', `${trusted.length} aprobadas solas${pendingReview ? ` · ${pendingReview} esperan tu revisión (pruebas que no pasaron todos los controles)` : ''}${unread}`)
  void read
  job.summary = 'Listo. El siguiente análisis usará estas reglas y pruebas.'
}

export function prepareView(repoId: string): PrepareView {
  return out(jobs.get(repoId))
}

/** Lanza el flujo; un texto = no se pudo (ya está corriendo). */
export function startPrepare(repoId: string): PrepareView | string {
  if (jobs.get(repoId)?.running) return '«Preparar todo» ya está corriendo en este proyecto'
  const job: Job = { running: true, steps: fresh(), summary: null, started_at: new Date().toISOString(), finished_at: null, cancelled: false }
  jobs.set(repoId, job)
  void flow(repoId, job)
    .catch((e: unknown) => {
      const stopped = e instanceof Stop && e.message === STOPPED
      const note = e instanceof Error ? e.message : 'Algo falló'
      job.steps = job.steps.map((s) => (s.status === 'haciendo' ? { ...s, status: stopped ? 'pendiente' : 'fallo', note: stopped ? STOPPED : note } : s))
    })
    .finally(() => {
      job.running = false
      job.finished_at = new Date().toISOString()
    })
  return out(job)
}

export function stopPrepare(repoId: string): PrepareView {
  const job = jobs.get(repoId)
  if (job?.running) job.cancelled = true
  return out(job)
}
