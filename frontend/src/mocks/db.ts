/**
 * "Backend" en memoria para desarrollar el front sin servidor. Imita al backend del Sprint 5 (clonar →
 * entorno → dependencias → Bandit → pip-audit → guardar el análisis con sus hallazgos de Seguridad) lo justo
 * para que la UI sea creíble.
 * El estado se reinicia al recargar la página.
 */
import type { Job, JobMessage } from '@/features/analysis/types'
import type { FindingCounts, Repo, SavedReport, TreeEntry } from '@/features/repos/types'
import type { ProjectConfig } from '@/features/settings/types'
import { JOB_STEPS } from '@/features/analysis/constants/jobSteps'
import { FILES } from './fixtures/code'

// ───────────────────────── Modelo interno ─────────────────────────

interface RepoRecord {
  id: string
  name: string
  url: string
  branch: string
  files: number
  status: Repo['status']
  error: string | null
  reports: SavedReport[]
  /** Contenido de cada archivo del último clon */
  content: Record<string, string>
  jobId: string | null
}

interface JobRecord extends Job {
  commit: string
  fail: 'clone' | 'python' | null
  timer: ReturnType<typeof setTimeout> | null
  listeners: Set<(m: JobMessage) => void>
  /** ms que tarda cada paso */
  speed: number[]
}

const DAY = 86_400_000
const now = Date.now()
const iso = (msAgo: number) => new Date(now - msAgo).toISOString()
const PY = (r: Record<string, string>) => Object.keys(r).filter((p) => p.endsWith('.py')).length

// ───────────────────────── Datos iniciales ─────────────────────────

function seedRepo(id: string, name: string, branch: string, history: { commit: string; agoMs: number; s: number; findings: FindingCounts }[]): RepoRecord {
  const files = PY(FILES)
  return {
    id,
    name,
    url: `https://github.com/${name}`,
    branch,
    files,
    status: 'listo',
    error: null,
    reports: history.map((h, i) => ({
      id: `${id}-${i + 1}`,
      num: i + 1,
      branch,
      commit: h.commit,
      created_at: iso(h.agoMs),
      duration_s: h.s,
      findings: h.findings,
      languages: [
        { name: 'Python', files },
        { name: 'Markdown', files: 1 },
      ],
    })),
    content: { ...FILES },
    jobId: null,
  }
}

const repos: RepoRecord[] = [
  seedRepo('r1', 'equipo/api-pagos', 'main', [
    { commit: 'f04b2d9', agoMs: 14 * DAY, s: 48, findings: { alta: 4, media: 3, baja: 2 } },
    { commit: '91ce07b', agoMs: 7 * DAY, s: 45, findings: { alta: 3, media: 3, baja: 2 } },
    { commit: 'a3f9c1e', agoMs: 2 * 3_600_000, s: 41, findings: { alta: 2, media: 3, baja: 1 } },
  ]),
  seedRepo('r2', 'equipo/etl-ventas', 'develop', [
    { commit: '5c1e8aa', agoMs: 3 * DAY, s: 52, findings: { alta: 1, media: 2, baja: 4 } },
    { commit: '7bd21aa', agoMs: DAY, s: 50, findings: { alta: 0, media: 1, baja: 3 } },
  ]),
  { id: 'r3', name: 'equipo/bot-soporte', url: 'https://github.com/equipo/bot-soporte', branch: 'main', files: 0, status: 'analizando', error: null, reports: [], content: {}, jobId: null },
  { id: 'r4', name: 'equipo/landing-web', url: 'https://github.com/equipo/landing-web', branch: 'main', files: 0, status: 'error', error: 'El repositorio no tiene código Python', reports: [], content: {}, jobId: null },
]

const configs: Record<string, ProjectConfig> = Object.fromEntries(
  repos.map((r) => [r.id, { weights: { seg: 50, test: 30, prac: 20 }, thresholds: { score: 70, cov: 60 }, ignored: ['B101'], excluded: ['migrations/', 'tests/fixtures/'] }]),
)

const jobs = new Map<string, JobRecord>()
let jobSeq = 0

// ───────────────────────── Vistas (DTO) ─────────────────────────

export class NotFound extends Error {}

export const getRepo = (id: string) => {
  const r = repos.find((x) => x.id === id)
  if (!r) throw new NotFound(`Repositorio ${id} no encontrado`)
  return r
}

export function repoView(r: RepoRecord): Repo {
  const last = r.reports.at(-1) ?? null
  const job = r.jobId ? jobs.get(r.jobId) : null
  return {
    id: r.id,
    name: r.name,
    url: r.url,
    branch: r.branch,
    commit: last?.commit ?? null,
    status: r.status,
    last_analyzed_at: last?.created_at ?? (r.status === 'error' ? iso(5 * DAY) : null),
    files: r.files,
    last_report_id: last?.id ?? null,
    last_report_num: last?.num ?? null,
    reports: r.reports.length,
    findings: last?.findings ?? null,
    error: r.error,
    progress: job && job.status === 'running' ? { job_id: job.id, step: job.step, total: job.total, name: JOB_STEPS[job.step]?.name ?? '' } : null,
  }
}

export const listRepos = () => repos.map(repoView)

export const history = (repoId: string) => [...getRepo(repoId).reports].reverse()

export function tree(repoId: string): TreeEntry[] {
  const repo = getRepo(repoId)
  return Object.keys(repo.content)
    .map((path) => ({ path, dir: path.includes('/') ? path.slice(0, path.lastIndexOf('/')) : '' }))
    .sort((a, b) => a.dir.localeCompare(b.dir) || a.path.localeCompare(b.path))
}

export function getFile(repoId: string, path: string) {
  const content = getRepo(repoId).content[path]
  if (content === undefined) throw new NotFound(`${path} no existe`)
  return content
}

// ───────────────────────── Configuración ─────────────────────────

export function getConfig(repoId: string) {
  getRepo(repoId)
  return configs[repoId]
}
export function saveConfig(repoId: string, cfg: ProjectConfig) {
  getRepo(repoId)
  configs[repoId] = cfg
  return cfg
}

// ───────────────────────── Jobs de análisis ─────────────────────────

function emit(job: JobRecord, m: JobMessage) {
  if (m.type === 'log') job.logs.push(m.line)
  job.listeners.forEach((l) => l(m))
}

const publicJob = (j: JobRecord): Job => ({
  id: j.id, url: j.url, name: j.name, branch: j.branch, step: j.step, total: j.total, status: j.status,
  logs: [...j.logs], error: j.error, repo_id: j.repo_id, report_id: j.report_id,
})

function startStep(job: JobRecord) {
  const s = JOB_STEPS[job.step]
  const command = s.command.replace('{branch}', job.branch).replace('{url}', job.url)
  emit(job, { type: 'step', index: job.step, total: job.total, name: s.name, command })
  emit(job, { type: 'log', line: `[${String(job.step + 1).padStart(2, '0')}/${job.total}] ${s.name} → ${command}` })
}

function repoOf(job: JobRecord) {
  let repo = repos.find((r) => r.name === job.name)
  if (!repo) {
    repo = { id: `r${repos.length + 1}`, name: job.name, url: job.url, branch: job.branch, files: 0, status: 'analizando', error: null, reports: [], content: {}, jobId: job.id }
    repos.push(repo)
    configs[repo.id] = structuredClone(configs.r1)
  }
  job.repo_id = repo.id
  return repo
}

function fail(job: JobRecord, error: NonNullable<Job['error']>, lines: string[]) {
  stop(job)
  job.status = 'error'
  job.error = error
  lines.forEach((line) => emit(job, { type: 'log', line }))
  emit(job, { type: 'error', step: job.step, ...error })
  const repo = repoOf(job)
  repo.status = 'error'
  repo.error = error.title
  repo.jobId = null
}

function finishJob(job: JobRecord) {
  const repo = repoOf(job)
  const num = (repo.reports.at(-1)?.num ?? 0) + 1
  const files = PY(FILES)
  const report: SavedReport = {
    id: `${repo.id}-${num}`, num, branch: job.branch, commit: job.commit, created_at: new Date().toISOString(), duration_s: 43,
    findings: { alta: 2, media: 3, baja: 1 },
    languages: [{ name: 'Python', files }, { name: 'Markdown', files: 1 }],
  }
  repo.reports.push(report)
  repo.content = { ...FILES }
  repo.files = files
  repo.status = 'listo'
  repo.error = null
  repo.branch = job.branch
  repo.jobId = null
  job.status = 'done'
  job.report_id = report.id
  emit(job, { type: 'log', line: `Análisis #${num} guardado en el repositorio con 6 hallazgo(s) de seguridad.` })
  emit(job, { type: 'done', repo_id: repo.id, report_id: report.id, num })
}

const SUMMARY: Record<number, (j: JobRecord) => string[]> = {
  0: (j) => [`  commit ${j.commit} · ${PY(FILES)} archivos .py · 1.8 s`, `  lenguajes: Python ${PY(FILES)} · Markdown 1`],
  1: () => ['  entorno listo en el sandbox WSL · Python 3.12.7 · copiados 11 archivos'],
  2: () => ['  Installed 14 packages in 1.2s'],
  3: () => ['  1 alta · 3 media · 1 baja'],
  4: () => ['  1 paquete(s) vulnerable(s)'],
}

function tick(job: JobRecord) {
  if (job.step === 0 && job.fail === 'clone') {
    return fail(job, { title: 'La rama no existe', detail: `fatal: Remote branch ${job.branch} not found in upstream origin`, hint: 'Revisa el nombre de la rama en GitHub y vuelve a intentarlo.' }, [
      `  ERROR: fatal: Remote branch ${job.branch} not found in upstream origin`,
    ])
  }
  if (job.step === 0 && job.fail === 'python') {
    return fail(
      job,
      { title: 'El repositorio no tiene código Python', detail: 'IA voy analiza proyectos Python y en este repositorio hay: JavaScript 14 · HTML 3 · CSS 2.', hint: 'Elige un repositorio con archivos .py (los notebooks .ipynb todavía no se analizan).' },
      ['  lenguajes: JavaScript 14 · HTML 3 · CSS 2', '  ERROR: IA voy analiza proyectos Python y en este repositorio hay: JavaScript 14 · HTML 3 · CSS 2.'],
    )
  }
  SUMMARY[job.step]?.(job).forEach((line) => emit(job, { type: 'log', line }))
  emit(job, { type: 'log', line: '  ✓ ok' })
  emit(job, { type: 'step_done', index: job.step })
  job.step++
  if (job.step >= job.total) {
    stop(job)
    finishJob(job)
  } else {
    startStep(job)
    job.timer = setTimeout(() => tick(job), stepMs(job))
  }
}

const stepMs = (job: JobRecord) => job.speed[Math.min(job.step, job.speed.length - 1)]

/** Velocidad de los pasos: `localStorage['iavoy-mock-speed'] = "800,60000"` (ms por paso) detiene el job en un paso para verlo. */
function defaultSpeed(): number[] {
  try {
    const custom = localStorage.getItem('iavoy-mock-speed')
    if (custom) return custom.split(',').map(Number)
  } catch {
    /* sin almacenamiento: velocidad normal */
  }
  return [1400]
}

function stop(job: JobRecord) {
  if (job.timer) clearTimeout(job.timer)
  job.timer = null
}

function run(job: JobRecord) {
  job.status = 'running'
  job.error = undefined
  startStep(job)
  job.timer = setTimeout(() => tick(job), stepMs(job))
}

interface JobOptions {
  fail?: JobRecord['fail']
  /** ms por paso (uno por paso; el último se repite) */
  speed?: number[]
}

export function startJob(url: string, branch: string, opts: JobOptions = {}) {
  const name = url.replace(/^https?:\/\/[^/]+\//, '').replace(/\.git$/, '').replace(/\/$/, '')
  const job: JobRecord = {
    id: `job-${++jobSeq}`, url, name, branch, step: 0, total: JOB_STEPS.length, status: 'running',
    logs: [`$ ia-voy analyze ${url} --branch ${branch}`],
    fail: opts.fail ?? (branch === 'no-existe' ? 'clone' : /landing|web|js/.test(name) ? 'python' : null),
    timer: null, listeners: new Set(), speed: opts.speed ?? defaultSpeed(), commit: Math.random().toString(16).slice(2, 9),
  }
  jobs.set(job.id, job)
  const repo = repoOf(job)
  repo.status = 'analizando'
  repo.error = null
  repo.jobId = job.id
  run(job)
  return job.id
}

export const reanalyze = (repoId: string) => {
  const r = getRepo(repoId)
  return startJob(r.url, r.branch)
}

export function getJob(jobId: string) {
  const j = jobs.get(jobId)
  if (!j) throw new NotFound('Job no encontrado')
  return j
}

export const jobSnapshot = (jobId: string) => publicJob(getJob(jobId))

export function retryJob(jobId: string) {
  const job = getJob(jobId)
  job.fail = null
  emit(job, { type: 'log', line: '— Reintentando —' })
  const repo = repoOf(job)
  repo.status = 'analizando'
  repo.error = null
  repo.jobId = job.id
  run(job)
}

export function cancelJob(jobId: string) {
  const job = getJob(jobId)
  stop(job)
  job.status = 'cancelled'
  const repo = repoOf(job)
  repo.status = repo.reports.length ? 'listo' : 'error'
  repo.error = repo.reports.length ? null : 'Análisis cancelado'
  repo.jobId = null
}

export function subscribe(jobId: string, listener: (m: JobMessage) => void) {
  const job = getJob(jobId)
  job.listeners.add(listener)
  listener({ type: 'snapshot', job: publicJob(job) })
  return () => job.listeners.delete(listener)
}

// El repo "bot-soporte" arranca con un análisis lento en curso
getRepo('r3').jobId = startJob('https://github.com/equipo/bot-soporte', 'main', { speed: [60_000] })
