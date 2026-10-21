/**
 * "Backend" en memoria para desarrollar el front sin servidor. Imita las reglas del backend real
 * (score ponderado, reglas ignoradas, re-análisis al guardar) lo justo para que la UI sea creíble.
 * El estado se reinicia al recargar la página.
 */
import type { Job, JobMessage } from '@/features/analysis/types'
import type { Finding, Patch } from '@/features/findings/types'
import type { Repo, TreeEntry } from '@/features/repos/types'
import type { PublicReport } from '@/features/public-report/types'
import type { Report } from '@/features/report/types'
import type { ProjectConfig } from '@/features/settings/types'
import { JOB_STEPS } from '@/features/analysis/constants/jobSteps'
import type { Category, Scores, Severity, Weights } from '@/shared/types/common'
import { calcScore } from '@/shared/utils/score'
import { FILES, lineAt } from './fixtures/code'
import { COMPLEXITY, COVERAGE, FINDINGS, FIXES, RESOLVED_BEFORE, type FindingTemplate } from './fixtures/findings'
import { demoUser } from './fixtures/user'

// ───────────────────────── Modelo interno ─────────────────────────

interface ReportRecord {
  id: string
  num: number
  repo_id: string
  branch: string
  commit: string
  created_at: string
  duration_s: number
  cat: Weights
  findings: FindingTemplate[]
  resolved: Set<number>
  coverage: typeof COVERAGE
  complexity: typeof COMPLEXITY
  summary: Report['summary']
}

interface RepoRecord {
  id: string
  name: string
  url: string
  branch: string
  files: number
  status: Repo['status']
  error: string | null
  /** Puntos de historia anteriores a los reportes guardados (para la tendencia) */
  history: { date: string; cat: Weights }[]
  reports: ReportRecord[]
  /** Contenido actual de cada archivo (el editor lo modifica) */
  content: Record<string, string>
  jobId: string | null
}

interface JobRecord extends Job {
  fail: boolean
  timer: ReturnType<typeof setInterval> | null
  listeners: Set<(m: JobMessage) => void>
  speed: number
}

interface ShareRecord {
  report_id: string
  password: string | null
  expires_at: string | null
  include_code: boolean
}

const DAY = 86_400_000
const now = Date.now()
const iso = (msAgo: number) => new Date(now - msAgo).toISOString()
const clamp = (v: number) => Math.max(0, Math.min(100, Math.round(v)))
const SEV_ORDER: Record<Severity, number> = { alta: 0, media: 1, baja: 2 }

// ───────────────────────── Datos iniciales ─────────────────────────

const OFFSETS: Record<Category, number[]> = { seg: [-8, -5, -1, 3, 6], test: [-5, -4, -2, -1, 0], prac: [-7, -4, -1, 3, 6] }

function seedRepo(
  id: string,
  name: string,
  branch: string,
  files: number,
  latest: { num: number; commit: string; agoMs: number; cat: Weights; ids: number[]; cov: number; failed: number; cc: number },
): RepoRecord {
  const findings = FINDINGS.filter((f) => latest.ids.includes(f.id))
  const mk = (num: number, agoMs: number, cat: Weights, list: FindingTemplate[], commit: string): ReportRecord => ({
    id: `${id}-${num}`,
    num,
    repo_id: id,
    branch,
    commit,
    created_at: iso(agoMs),
    duration_s: 120 + ((num * 37) % 90),
    cat,
    findings: list,
    resolved: new Set(),
    coverage: COVERAGE,
    complexity: COMPLEXITY,
    summary: { coverage_total: latest.cov, tests_failed: latest.failed, avg_complexity: latest.cc },
  })
  const prevCat: Weights = { seg: clamp(latest.cat.seg - 8), test: clamp(latest.cat.test - 1), prac: clamp(latest.cat.prac - 7) }
  // Reporte anterior: sin los hallazgos 2, 3 y 7 y con dos que luego se resolvieron
  const prevFindings = [...findings.filter((f) => ![2, 3, 7].includes(f.id)), ...RESOLVED_BEFORE]
  const reports = [
    mk(latest.num - 8, latest.agoMs + 14 * DAY, { seg: clamp(latest.cat.seg - 5), test: clamp(latest.cat.test - 4), prac: clamp(latest.cat.prac - 4) }, prevFindings, 'f04b2d9'),
    mk(latest.num - 1, latest.agoMs + 7 * DAY, prevCat, prevFindings, '91ce07b'),
    mk(latest.num, latest.agoMs, latest.cat, findings, latest.commit),
  ]
  return {
    id,
    name,
    url: `https://github.com/${name}`,
    branch,
    files,
    status: 'listo',
    error: null,
    history: [4, 3, 2, 1].map((w, i) => ({
      date: iso(latest.agoMs + (w + 2) * 7 * DAY),
      cat: { seg: clamp(latest.cat.seg + OFFSETS.seg[i]), test: clamp(latest.cat.test + OFFSETS.test[i]), prac: clamp(latest.cat.prac + OFFSETS.prac[i]) },
    })),
    reports,
    content: { ...FILES },
    jobId: null,
  }
}

const repos: RepoRecord[] = [
  seedRepo('r1', 'equipo/api-pagos', 'main', 48, { num: 128, commit: 'a3f9c1e', agoMs: 2 * 3_600_000, cat: { seg: 68, test: 85, prac: 73 }, ids: FINDINGS.map((f) => f.id), cov: 78, failed: 1, cc: 6.2 }),
  seedRepo('r2', 'equipo/etl-ventas', 'develop', 31, { num: 97, commit: '7bd21aa', agoMs: DAY, cat: { seg: 92, test: 84, prac: 86 }, ids: [4, 9, 10, 12], cov: 81, failed: 0, cc: 4.1 }),
  seedRepo('r3', 'equipo/bot-soporte', 'main', 22, { num: 64, commit: 'e01c4f2', agoMs: 3 * DAY, cat: { seg: 48, test: 61, prac: 66 }, ids: [1, 2, 5, 6, 7, 8, 11], cov: 52, failed: 3, cc: 8.7 }),
  { id: 'r4', name: 'equipo/notebooks-ml', url: 'https://github.com/equipo/notebooks-ml', branch: 'feature/limpieza', files: 17, status: 'analizando', error: null, history: [], reports: [], content: { ...FILES }, jobId: null },
  { id: 'r5', name: 'equipo/cli-utilidades', url: 'https://github.com/equipo/cli-utilidades', branch: 'main', files: 12, status: 'error', error: 'pytest no pudo importar el módulo "click"', history: [], reports: [], content: { ...FILES }, jobId: null },
]

const configs: Record<string, ProjectConfig> = Object.fromEntries(
  repos.map((r) => [r.id, { weights: { seg: 50, test: 30, prac: 20 }, thresholds: { score: 70, cov: 60 }, ignored: ['S101', 'D100'], excluded: ['migrations/', 'tests/fixtures/'] }]),
)

const jobs = new Map<string, JobRecord>()
const shares = new Map<string, ShareRecord>()
const shareTokens = new Map<string, string>()
let jobSeq = 0

// ───────────────────────── Vistas (DTO) ─────────────────────────

export class NotFound extends Error {}

export const getRepo = (id: string) => {
  const r = repos.find((x) => x.id === id)
  if (!r) throw new NotFound(`Repositorio ${id} no encontrado`)
  return r
}

const config = (repoId: string) => configs[repoId]
const latestReport = (r: RepoRecord) => r.reports.at(-1) ?? null
const scoresOf = (repoId: string, cat: Weights): Scores => ({ ...cat, global: Math.round(calcScore(config(repoId).weights, cat) * 10) / 10 })

function findReport(repoId: string, reportId: string) {
  const r = getRepo(repoId)
  const rep = reportId === 'latest' ? latestReport(r) : r.reports.find((x) => x.id === reportId)
  if (!rep) throw new NotFound('Reporte no encontrado')
  return { repo: r, report: rep }
}

function findingView(report: ReportRecord, f: FindingTemplate, withCode = true): Finding {
  const content = FILES[f.file]
  const snippet =
    withCode && content
      ? content
          .split('\n')
          .map((text, i) => ({ line: i + 1, text }))
          .filter((l) => Math.abs(l.line - f.line) <= 2)
      : undefined
  return { ...f, status: report.resolved.has(f.id) ? 'resolved' : 'open', snippet }
}

/** Hallazgos visibles: sin las reglas ignoradas en la configuración, ordenados por severidad. */
const visibleFindings = (repo: RepoRecord, report: ReportRecord, withCode = true) =>
  report.findings
    .filter((f) => !config(repo.id).ignored.includes(f.rule))
    .map((f) => findingView(report, f, withCode))
    .sort((a, b) => SEV_ORDER[a.sev] - SEV_ORDER[b.sev])

export function repoView(r: RepoRecord): Repo {
  const rep = latestReport(r)
  const job = r.jobId ? jobs.get(r.jobId) : null
  return {
    id: r.id,
    name: r.name,
    url: r.url,
    branch: r.branch,
    commit: rep?.commit ?? null,
    status: r.status,
    last_analyzed_at: rep?.created_at ?? (r.status === 'error' ? iso(5 * DAY) : null),
    files: r.files,
    last_report_id: rep?.id ?? null,
    last_report_num: rep?.num ?? null,
    scores: rep ? scoresOf(r.id, rep.cat) : null,
    error: r.error,
    progress: job && job.status === 'running' ? { job_id: job.id, step: job.step, total: job.total, name: JOB_STEPS[job.step]?.name ?? '' } : null,
  }
}

export const listRepos = () => repos.map(repoView)

export function reportView(repoId: string, reportId: string): Report {
  const { repo, report } = findReport(repoId, reportId)
  const idx = repo.reports.indexOf(report)
  const prev = idx > 0 ? repo.reports[idx - 1] : null
  const cfg = config(repoId)
  return {
    id: report.id,
    num: report.num,
    repo_id: repo.id,
    repo_name: repo.name,
    branch: report.branch,
    commit: report.commit,
    created_at: report.created_at,
    duration_s: report.duration_s,
    scores: scoresOf(repoId, report.cat),
    prev: prev ? { num: prev.num, scores: scoresOf(repoId, prev.cat) } : null,
    weights: cfg.weights,
    thresholds: cfg.thresholds,
    findings: visibleFindings(repo, report),
    coverage: report.coverage,
    complexity: report.complexity,
    summary: report.summary,
    analyzers: ['bandit', 'pip-audit', 'pytest', 'coverage', 'ruff', 'radon'],
    languages: [{ name: 'Python', files: repo.files }],
  }
}

export function dashboard(repoId: string | null) {
  const ready = repos.filter((r) => r.reports.length)
  const repo = ready.find((r) => r.id === repoId) ?? ready[0]
  const base = { active_repos: ready.length, repos: listRepos(), thresholds: repo ? config(repo.id).thresholds : { score: 70, cov: 60 } }
  if (!repo) return { ...base, selected: null }
  const rep = latestReport(repo)!
  const prev = repo.reports.at(-2) ?? null
  const open = visibleFindings(repo, rep).filter((f) => f.status === 'open')
  const history = [
    ...repo.history.map((h) => ({ date: h.date, ...scoresOf(repo.id, h.cat) })),
    ...repo.reports.slice(-3).map((x) => ({ date: x.created_at, ...scoresOf(repo.id, x.cat) })),
  ]
  return {
    ...base,
    selected: {
      repo: repoView(repo),
      report_id: rep.id,
      num: rep.num,
      scores: scoresOf(repo.id, rep.cat),
      prev_scores: prev ? scoresOf(repo.id, prev.cat) : null,
      history,
      top_findings: open.slice(0, 4),
      open_findings: open.length,
    },
  }
}

export function tree(repoId: string): TreeEntry[] {
  const repo = getRepo(repoId)
  const rep = latestReport(repo)
  const open = rep ? visibleFindings(repo, rep).filter((f) => f.status === 'open') : []
  return Object.keys(repo.content)
    .filter((p) => p !== 'README.md')
    .map((path) => {
      const mine = open.filter((f) => f.file === path)
      return {
        path,
        dir: path.includes('/') ? path.split('/')[0] : '',
        open_findings: mine.length,
        worst: mine.length ? mine.reduce((w, f) => (SEV_ORDER[f.sev] < SEV_ORDER[w] ? f.sev : w), 'baja' as Severity) : null,
      }
    })
    .sort((a, b) => a.dir.localeCompare(b.dir) || a.path.localeCompare(b.path))
}

// ───────────────────────── Editor y correcciones ─────────────────────────

export function getFile(repoId: string, path: string) {
  const content = getRepo(repoId).content[path]
  if (content === undefined) throw new NotFound(`${path} no existe`)
  return content
}

export function fixPatches(findingIds: number[]): Patch[] {
  return findingIds.flatMap((id) => (FIXES[id] ?? []).map(([file, line, text]) => ({ file, line, original: lineAt(FILES[file], line), text })))
}

/** Guarda y "re-analiza": un hallazgo queda resuelto si su línea original ya no está en el archivo. */
export function saveFile(repoId: string, path: string, content: string) {
  const repo = getRepo(repoId)
  const rep = latestReport(repo)
  repo.content[path] = content
  if (!rep) return { resolved_ids: [], score_before: 0, score_after: 0 }

  const before = scoresOf(repoId, rep.cat).global
  const lines = new Set(content.split('\n'))
  const resolved: number[] = []
  for (const f of rep.findings) {
    if (f.file !== path || rep.resolved.has(f.id) || !FIXES[f.id]) continue
    const evidence = lineAt(FILES[path], f.line)
    if (lines.has(evidence)) continue
    rep.resolved.add(f.id)
    resolved.push(f.id)
    if (f.cat === 'seg') rep.cat.seg = clamp(rep.cat.seg + (f.sev === 'alta' ? 7 : 4))
    else if (f.cat === 'prac') rep.cat.prac = clamp(rep.cat.prac + 3)
    else rep.cat.test = clamp(rep.cat.test + 2)
  }
  return { resolved_ids: resolved, score_before: before, score_after: scoresOf(repoId, rep.cat).global }
}

// ───────────────────────── Configuración ─────────────────────────

export function getConfig(repoId: string) {
  getRepo(repoId)
  return config(repoId)
}
export function saveConfig(repoId: string, cfg: ProjectConfig) {
  getRepo(repoId)
  configs[repoId] = cfg
  return cfg
}

// ───────────────────────── Comparativa ─────────────────────────

export function analyses(repoId: string) {
  const repo = getRepo(repoId)
  const fmt = (d: string) => new Intl.DateTimeFormat('es', { day: '2-digit', month: 'short' }).format(new Date(d))
  return [...repo.reports].reverse().map((r) => ({ id: r.id, label: `#${r.num} · ${fmt(r.created_at)} · ${r.branch}` }))
}

export function diff(base: string, target: string) {
  const repoId = base.split('-')[0]
  const a = findReport(repoId, base)
  const b = findReport(repoId, target)
  const open = (rep: ReportRecord) => rep.findings.filter((f) => !rep.resolved.has(f.id))
  const aIds = new Set(open(a.report).map((f) => f.id))
  const bIds = new Set(open(b.report).map((f) => f.id))
  return {
    a: scoresOf(repoId, a.report.cat),
    b: scoresOf(repoId, b.report.cat),
    new: open(b.report).filter((f) => !aIds.has(f.id)).map((f) => findingView(b.report, f, false)),
    resolved: open(a.report).filter((f) => !bIds.has(f.id)).map((f) => ({ ...findingView(a.report, f, false), status: 'resolved' as const })),
  }
}

// ───────────────────────── Compartir ─────────────────────────

export function createShare(reportId: string, password: string | null, days: number, include_code: boolean) {
  const share_id = Math.random().toString(16).slice(2, 8)
  const expires_at = days ? new Date(Date.now() + days * DAY).toISOString() : null
  shares.set(share_id, { report_id: reportId, password: password || null, expires_at, include_code })
  return { share_id, url: `${window.location.origin}/r/${share_id}`, expires_at }
}

export type PublicResult = { ok: true; data: PublicReport } | { ok: false; status: number; code: string; message: string }

export function publicReport(shareId: string, token: string | null): PublicResult {
  const s = shares.get(shareId)
  if (!s) return { ok: false, status: 404, code: 'not_found', message: 'Este enlace no existe' }
  if (s.expires_at && new Date(s.expires_at).getTime() < Date.now()) return { ok: false, status: 410, code: 'expired', message: 'Este enlace expiró' }
  if (s.password && shareTokens.get(shareId) !== token) return { ok: false, status: 401, code: 'password_required', message: 'Este reporte está protegido' }
  const repoId = s.report_id.split('-')[0]
  const { repo, report } = findReport(repoId, s.report_id)
  return {
    ok: true,
    data: {
      repo_name: repo.name,
      branch: report.branch,
      commit: report.commit,
      created_at: report.created_at,
      scores: scoresOf(repoId, report.cat),
      findings: visibleFindings(repo, report, s.include_code).filter((f) => f.sev !== 'baja' && f.status === 'open'),
      shared_by: demoUser.name,
      expires_at: s.expires_at,
      include_code: s.include_code,
    },
  }
}

export function unlockShare(shareId: string, password: string) {
  const s = shares.get(shareId)
  if (!s || s.password !== password) return null
  const token = Math.random().toString(36).slice(2)
  shareTokens.set(shareId, token)
  return token
}

// ───────────────────────── Jobs de análisis ─────────────────────────

const STEP_SUMMARY: Record<number, (j: JobRecord) => string> = {
  3: () => '  3 alta · 4 media · 0 baja',
  4: () => '  1 paquete vulnerable',
  5: () => '  139 passed, 1 failed, 3 skipped',
  6: () => '  cobertura total: 78 %',
  7: () => '  4 problemas (3 corregibles)',
  8: () => '  complejidad media: 6.2',
}

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

function finishJob(job: JobRecord) {
  let repo = repos.find((r) => r.name === job.name)
  if (!repo) {
    repo = { id: `r${repos.length + 1}`, name: job.name, url: job.url, branch: job.branch, files: 20, status: 'listo', error: null, history: [], reports: [], content: { ...FILES }, jobId: null }
    repos.push(repo)
    configs[repo.id] = structuredClone(configs.r1)
  }
  const last = latestReport(repo)
  const num = (last?.num ?? 0) + 1
  const report: ReportRecord = {
    id: `${repo.id}-${num}`, num, repo_id: repo.id, branch: job.branch, commit: Math.random().toString(16).slice(2, 9),
    created_at: new Date().toISOString(), duration_s: 168,
    cat: last ? { ...last.cat } : { seg: 71, test: 77, prac: 80 },
    findings: last ? last.findings.filter((f) => !last.resolved.has(f.id)) : FINDINGS.filter((f) => f.sev !== 'baja'),
    resolved: new Set(), coverage: COVERAGE, complexity: COMPLEXITY,
    summary: last?.summary ?? { coverage_total: 74, tests_failed: 1, avg_complexity: 5.4 },
  }
  repo.reports.push(report)
  repo.status = 'listo'
  repo.error = null
  repo.branch = job.branch
  repo.jobId = null
  job.status = 'done'
  job.repo_id = repo.id
  job.report_id = report.id
  emit(job, { type: 'log', line: `Análisis #${num} completado.` })
  emit(job, { type: 'done', repo_id: repo.id, report_id: report.id, num, score: scoresOf(repo.id, report.cat).global })
}

function tick(job: JobRecord) {
  if (job.fail && job.step === 5) {
    stop(job)
    job.status = 'error'
    job.error = { title: 'pytest no pudo importar un módulo', detail: "ModuleNotFoundError: No module named 'stripe'", hint: 'Falta stripe en requirements.txt. Agrégalo y vuelve a intentar.' }
    emit(job, { type: 'log', line: "  ERROR: ModuleNotFoundError: No module named 'stripe'" })
    emit(job, { type: 'log', line: '  El análisis se detuvo. Revisa requirements.txt.' })
    emit(job, { type: 'error', step: job.step, ...job.error })
    const repo = repos.find((r) => r.name === job.name)
    if (repo) {
      repo.status = 'error'
      repo.error = 'pytest no pudo importar el módulo "stripe"'
    }
    return
  }
  const summary = STEP_SUMMARY[job.step]
  if (summary) emit(job, { type: 'log', line: summary(job) })
  emit(job, { type: 'log', line: '  ✓ ok' })
  emit(job, { type: 'step_done', index: job.step })
  job.step++
  if (job.step >= job.total) {
    stop(job)
    finishJob(job)
  } else startStep(job)
}

function stop(job: JobRecord) {
  if (job.timer) clearInterval(job.timer)
  job.timer = null
}

function run(job: JobRecord) {
  job.status = 'running'
  job.error = undefined
  startStep(job)
  job.timer = setInterval(() => tick(job), job.speed)
}

export function startJob(url: string, branch: string, opts: { fail?: boolean; speed?: number } = {}) {
  const name = url.replace(/^https?:\/\/[^/]+\//, '').replace(/\.git$/, '')
  const job: JobRecord = {
    id: `job-${++jobSeq}`, url, name, branch, step: 0, total: JOB_STEPS.length, status: 'running',
    logs: [`$ ia-voy analyze ${url} --branch ${branch}`], fail: opts.fail ?? /error|cli-utilidades/.test(url),
    timer: null, listeners: new Set(), speed: opts.speed ?? 750,
  }
  jobs.set(job.id, job)
  const repo = repos.find((r) => r.name === name)
  if (repo) {
    repo.status = 'analizando'
    repo.error = null
    repo.jobId = job.id
    job.repo_id = repo.id
  }
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
  job.fail = false
  emit(job, { type: 'log', line: '— Reintentando —' })
  const repo = repos.find((r) => r.name === job.name)
  if (repo) {
    repo.status = 'analizando'
    repo.error = null
    repo.jobId = job.id
  }
  run(job)
}

export function cancelJob(jobId: string) {
  const job = getJob(jobId)
  stop(job)
  job.status = 'cancelled'
  const repo = repos.find((r) => r.name === job.name)
  if (repo) {
    repo.status = repo.reports.length ? 'listo' : 'error'
    repo.error = repo.reports.length ? null : 'Análisis cancelado'
    repo.jobId = null
  }
}

export function subscribe(jobId: string, listener: (m: JobMessage) => void) {
  const job = getJob(jobId)
  job.listeners.add(listener)
  listener({ type: 'snapshot', job: publicJob(job) })
  return () => job.listeners.delete(listener)
}

// El repo "notebooks-ml" arranca con un análisis lento en curso
getRepo('r4').jobId = startJob('https://github.com/equipo/notebooks-ml', 'feature/limpieza', { speed: 4000 })
