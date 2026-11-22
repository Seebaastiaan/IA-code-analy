import { delay, http, HttpResponse, ws, type HttpResponseResolver, type PathParams } from 'msw'
import type { AnalyzeRequest } from '@/features/analysis/types'
import type { ChatRequest } from '@/features/assistant/types'
import type { GithubCallbackRequest } from '@/features/auth/types'
import type { DiffRequest } from '@/features/compare/types'
import type { SaveFileRequest } from '@/features/editor/types'
import type { FixRequest } from '@/features/findings/types'
import type { ProjectConfig } from '@/features/settings/types'
import type { ImportRulesRequest } from '@/features/rules/types'
import type { ShareRequest } from '@/features/share/types'
import { EP } from '@/shared/api/endpoints'
import * as db from '../db'
import * as github from '../github'
import * as harness from '../harness'
import * as ruleTests from '../ruleTests'
import * as rules from '../rules'
import * as team from '../team'
import { answer } from '../fixtures/chat'
import { languageOf } from '../fixtures/code'
import { health } from '../fixtures/health'
import { demoUser } from '../fixtures/user'

const fail = (status: number, code: string, message: string) => HttpResponse.json({ error: { code, message } }, { status })

/** Envuelve un handler: latencia realista y NotFound → 404. */
function route<P extends PathParams = PathParams>(fn: HttpResponseResolver<P>, ms = 250): HttpResponseResolver<P> {
  return async (info) => {
    await delay(ms)
    try {
      return await fn(info)
    } catch (e) {
      if (e instanceof db.NotFound) return fail(404, 'not_found', e.message)
      throw e
    }
  }
}

const param = (request: Request, key: string) => new URL(request.url).searchParams.get(key)

const json = HttpResponse.json

// El WebSocket vive en el mismo origen que la app (igual que con el proxy de Vite)
const jobsSocket = ws.link(`${window.location.origin.replace(/^http/, 'ws')}/ws/jobs/:jobId`)

export const handlers = [
  // ─── Auth ───
  // Login con GitHub simulado: authorize vuelve directo a /github/callback sin pasar por GitHub
  http.post(EP.auth.githubAuthorize, route(() => json(github.authorize()))),
  http.post(EP.auth.githubCallback, route(async ({ request }) => {
    const body = (await request.json()) as GithubCallbackRequest
    if (!github.consumeState(body.state)) return fail(400, 'invalid_state', 'El inicio de sesión expiró o no es válido. Vuelve a intentarlo.')
    return json({ token: 'mock-token', user: demoUser })
  }, 700)),
  http.post(EP.auth.logout, () => new HttpResponse(null, { status: 204 })),
  http.get(EP.auth.me, () => json(demoUser)),
  http.get(EP.health, () => json(health)),

  // ─── Tablero y repos ───
  http.get(EP.dashboard, route(({ request }) => json(db.dashboard(param(request, 'repo'))))),
  http.get(EP.repos.list, route(() => json(db.listRepos()))),
  http.delete(EP.repos.remove(':repoId'), route(({ params }) => {
    const busy = db.deleteRepo(params.repoId as string)
    return busy ? fail(409, 'analysis_running', busy) : new HttpResponse(null, { status: 204 })
  })),
  http.post(EP.repos.analyze(':repoId'), route(({ params }) => json({ job_id: db.reanalyze(params.repoId as string) }))),
  http.get(EP.repos.tree(':repoId'), route(({ params }) => json(db.tree(params.repoId as string)))),
  http.get(EP.repos.analyses(':repoId'), route(({ params }) => json(db.analyses(params.repoId as string)))),
  http.get(EP.repos.index(':repoId'), route(({ params }) => {
    const repo = db.getRepo(params.repoId as string)
    return json({ status: 'ready', py_files: repo.files, chunks: repo.files * 13, readme: true, report_num: repo.reports.at(-1)?.num ?? null, model: 'Gemini 2.5 Flash', fallback: 'Groq · Llama 3.3' })
  })),

  // ─── GitHub ───
  http.get(EP.github.status, route(() => json(github.status()))),
  http.get(EP.github.repos, route(({ request }) => json(github.repos(param(request, 'q'))))),
  http.get(EP.github.branches(':owner/:repo'), route(({ params }) => {
    const list = github.branches(`${params.owner}/${params.repo}`)
    return list ? json(list) : fail(404, 'not_found', 'Repositorio no encontrado')
  })),

  // ─── Análisis ───
  http.post(EP.analyze, route(async ({ request }) => {
    const body = (await request.json()) as AnalyzeRequest
    if (!/^https?:\/\/.+\/.+/.test(body.url)) return fail(422, 'invalid_url', 'La URL del repositorio no es válida')
    const invalid = body.rules === undefined ? null : rules.fromAnalyze(body.url, body.rules)
    if (invalid) return fail(422, 'invalid_rules', invalid)
    return json({ job_id: db.startJob(body.url, body.branch || 'main') })
  }, 400)),
  http.get(EP.jobs.get(':jobId'), route(({ params }) => json(db.jobSnapshot(params.jobId as string)))),
  http.delete(EP.jobs.get(':jobId'), route(({ params }) => {
    db.cancelJob(params.jobId as string)
    return new HttpResponse(null, { status: 204 })
  })),
  http.post(EP.jobs.retry(':jobId'), route(({ params }) => {
    db.retryJob(params.jobId as string)
    return json({ job_id: params.jobId })
  })),
  jobsSocket.addEventListener('connection', ({ client, params }) => {
    try {
      const unsubscribe = db.subscribe(params.jobId as string, (m) => client.send(JSON.stringify(m)))
      client.addEventListener('close', unsubscribe)
    } catch {
      client.close(4404, 'Job no encontrado')
    }
  }),

  // ─── Reporte ───
  http.get(EP.report.get(':reportId'), route(({ request, params }) => {
    const repo = param(request, 'repo') ?? (params.reportId as string).split('-')[0]
    return json(db.reportView(repo, params.reportId as string))
  })),
  http.get(EP.report.export(':reportId'), route(({ request, params }) => {
    const id = params.reportId as string
    const format = param(request, 'format') ?? 'json'
    const report = db.reportView(id.split('-')[0], id)
    const body =
      format === 'md'
        ? `# ${report.repo_name} · #${report.num}\n\nScore: ${report.scores.global}\n\n${report.findings.map((f) => `- [${f.sev}] ${f.rule} ${f.file}:${f.line} — ${f.msg}`).join('\n')}\n`
        : format === 'html'
          ? `<!doctype html><meta charset="utf-8"><title>${report.repo_name}</title><h1>${report.repo_name} · #${report.num}</h1><p>Score ${report.scores.global}</p>`
          : JSON.stringify(format === 'sarif' ? { version: '2.1.0', runs: [{ tool: { driver: { name: 'IA voy' } }, results: report.findings.map((f) => ({ ruleId: f.rule, message: { text: f.msg }, locations: [{ physicalLocation: { artifactLocation: { uri: f.file }, region: { startLine: f.line } } }] })) }] } : report, null, 2)
    const ext = format === 'sarif' ? 'sarif.json' : format
    return new HttpResponse(body, { headers: { 'Content-Type': 'application/octet-stream', 'Content-Disposition': `attachment; filename="reporte-${id}.${ext}"` } })
  })),
  http.post(EP.report.share(':reportId'), route(async ({ request, params }) => {
    const body = (await request.json()) as ShareRequest
    return json(db.createShare(params.reportId as string, body.password, body.expires_days, body.include_code))
  })),

  // ─── Editor ───
  http.get(EP.file, route(({ request }) => {
    const path = param(request, 'path') ?? ''
    return json({ path, language: languageOf(path), content: db.getFile(param(request, 'repo') ?? '', path) })
  })),
  http.put(EP.file, route(async ({ request }) => {
    const body = (await request.json()) as SaveFileRequest
    return json(db.saveFile(body.repo_id, body.path, body.content))
  }, 1200)),
  http.post(EP.fix, route(async ({ request }) => {
    const body = (await request.json()) as FixRequest
    return json({ patches: db.fixPatches(body.finding_ids), notes: db.fixNotes(body.finding_ids) })
  })),

  // ─── Asistente ───
  http.post(EP.chat, route(async ({ request }) => {
    const body = (await request.json()) as ChatRequest
    return json(answer(body.message))
  }, 1100)),
  // Igual que el backend: Server-Sent Events con trozos de la respuesta y al final la respuesta completa
  http.post(EP.chatStream, route(async ({ request }) => {
    const body = (await request.json()) as ChatRequest
    const res = answer(body.message)
    const words = res.content.split(/(?<= )/)
    const encoder = new TextEncoder()
    const sse = (event: string, data: unknown) => encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
    const stream = new ReadableStream({
      async start(controller) {
        for (let i = 0; i < words.length; i += 4) {
          controller.enqueue(sse('delta', { text: words.slice(i, i + 4).join('') }))
          await delay(60)
        }
        controller.enqueue(sse('done', res))
        controller.close()
      },
    })
    return new HttpResponse(stream, { headers: { 'Content-Type': 'text/event-stream' } })
  }, 700)),

  // ─── Comparativa ───
  http.post(EP.diff, route(async ({ request }) => {
    const body = (await request.json()) as DiffRequest
    return json(db.diff(body.base, body.target))
  })),

  // ─── Configuración ───
  http.get(EP.config(':projectId'), route(({ params }) => json(db.getConfig(params.projectId as string)))),
  http.put(EP.config(':projectId'), route(async ({ request, params }) => json(db.saveConfig(params.projectId as string, (await request.json()) as ProjectConfig)))),

  // ─── Reglas de negocio ───
  http.get(EP.report.rules(':reportId'), route(({ request, params }) => {
    const repo = param(request, 'repo') ?? (params.reportId as string).split('-')[0]
    return json(rules.reportRules(repo, params.reportId as string))
  })),
  http.get(EP.rules.project(':projectId'), route(({ params }) => json(rules.projectRules(params.projectId as string)))),
  http.put(EP.rules.project(':projectId'), route(async ({ request, params }) => {
    const { content } = (await request.json()) as { content: string }
    const saved = rules.upload(params.projectId as string, content)
    return typeof saved === 'string' ? fail(422, 'invalid_rules', saved) : json(saved)
  })),
  http.post(EP.rules.states(':projectId'), route(async ({ request, params }) => {
    const { ids, status, by } = (await request.json()) as { ids: string[]; status: 'borrador' | 'aprobada'; by?: 'equipo' | 'programa' }
    const done = rules.setStates(params.projectId as string, ids, status, by)
    return typeof done === 'string' ? fail(409, 'no_rules', done) : json(done)
  })),
  http.put(EP.rules.doubts(':projectId', ':ruleId'), route(async ({ request, params }) => {
    const { doubts } = (await request.json()) as { doubts: string[] }
    const done = rules.setDoubts(params.projectId as string, params.ruleId as string, doubts)
    return typeof done === 'string' ? fail(409, 'no_rules', done) : json(done)
  })),
  http.get(EP.rules.control(':projectId'), route(({ params }) => json(rules.concordance(params.projectId as string)))),
  http.put(EP.rules.expected(':projectId', ':ruleId'), route(async ({ request, params }) => {
    const { expected } = (await request.json()) as { expected: 'cumple' | 'viola' | null }
    const done = rules.setExpected(params.projectId as string, params.ruleId as string, expected)
    return typeof done === 'string' ? fail(404, 'unknown_rule', done) : json(done)
  })),
  http.post(EP.rules.write(':projectId'), route(async ({ request, params }) => {
    const { text } = (await request.json()) as { text: string }
    const done = rules.writeRule(params.projectId as string, text)
    return typeof done === 'string' ? fail(422, 'invalid_sentence', done) : json(done)
  })),
  http.post(EP.rules.testFixCode(':projectId', ':ruleId'), route(() => fail(409, 'fix_unavailable', 'La corrección del código con IA no está disponible en la demo'))),
  http.post(EP.rules.answer(':projectId', ':ruleId'), route(async ({ request, params }) => {
    const { doubt, answer } = (await request.json()) as { doubt: string; answer: string }
    const done = rules.answerDoubt(params.projectId as string, params.ruleId as string, doubt, answer)
    return typeof done === 'string' ? fail(409, 'unknown_doubt', done) : json(done)
  })),
  http.delete(EP.rules.project(':projectId'), route(({ params }) => json(rules.remove(params.projectId as string)))),
  http.post(EP.rules.validate(':projectId'), route(async ({ request, params }) => json(rules.validateFor(params.projectId as string, ((await request.json()) as { content: string }).content)))),
  http.get(EP.rules.document(':projectId'), route(({ params, request }) => {
    const doc = rules.documentFor(params.projectId as string, param(request, 'formato') ?? 'html')
    return typeof doc === 'string' ? fail(409, 'no_rules', doc) : new HttpResponse(doc.body, { headers: { 'Content-Type': doc.type, 'Content-Disposition': `attachment; filename="${doc.name}"` } })
  })),
  http.get(EP.rules.template(':projectId'), route(({ params }) => new HttpResponse(rules.templateFor(params.projectId as string), { headers: { 'Content-Type': 'application/toml', 'Content-Disposition': 'attachment; filename="reglas_negocio.toml"' } }))),
  http.post(EP.rules.precheck, route(async ({ request }) => {
    const body = (await request.json()) as { url: string; branch: string; content?: string }
    const result = rules.precheck(body.url, body.branch, body.content)
    return result ? json(result) : fail(422, 'invalid_url', 'Usa la URL de un repositorio de GitHub (ej. https://github.com/equipo/proyecto)')
  })),
  // Leer el documento con IA tarda: se simula una espera más larga
  http.post(EP.rules.import, route(async ({ request }) => {
    const result = rules.importDocument((await request.json()) as ImportRulesRequest)
    return typeof result === 'string' ? fail(415, 'unsupported_type', result) : json(result)
  }, 1200)),
  // Mapa y arnés de pruebas: la IA tarda en proponer el arnés; la prueba de humo corre unos segundos
  http.get(EP.rules.harness(':projectId'), route(({ params }) => json(harness.harnessView(params.projectId as string)))),
  http.post(EP.rules.harness(':projectId'), route(({ params }) => json(harness.proposeHarness(params.projectId as string)), 1500)),
  http.post(EP.rules.harnessFromRepo(':projectId'), route(() => fail(404, 'no_repo_harness', 'El repo no tiene un conftest.py con los fixtures `api` y `como`'))),
  http.put(EP.rules.harness(':projectId'), route(async ({ request, params }) => {
    const view = harness.editHarness(params.projectId as string, ((await request.json()) as { code: string }).code)
    return view ? json(view) : fail(404, 'no_harness', 'Todavía no hay arnés: propónlo con la IA o usa el del repo')
  })),
  http.delete(EP.rules.harness(':projectId'), route(({ params }) => json(harness.removeHarness(params.projectId as string)))),
  http.post(EP.rules.harnessSmoke(':projectId'), route(({ params }) => {
    const view = harness.runSmoke(params.projectId as string)
    return typeof view === 'string' ? fail(422, 'invalid_harness', view) : json(view)
  })),
  http.post(EP.rules.harnessApprove(':projectId'), route(({ params }) => {
    const view = harness.approveHarness(params.projectId as string, demoUser.name)
    return typeof view === 'string' ? fail(409, 'smoke_required', view) : json(view)
  })),
  // Pruebas de las reglas: generar y correr siguen en segundo plano (la vista se consulta cada 2 s)
  http.get(EP.rules.tests(':projectId'), route(({ params }) => json(ruleTests.ruleTestsView(params.projectId as string)))),
  http.post(EP.rules.tests(':projectId'), route(async ({ request, params }) => {
    const { ids } = (await request.json()) as { ids: string[] | null }
    const view = ruleTests.generateTests(params.projectId as string, ids)
    return typeof view === 'string' ? fail(409, 'tests_busy', view) : json(view)
  })),
  http.post(EP.rules.testsRun(':projectId'), route(async ({ request, params }) => {
    const { ids } = (await request.json()) as { ids: string[] | null }
    const view = ruleTests.runTests(params.projectId as string, ids)
    return typeof view === 'string' ? fail(409, 'nothing_to_run', view) : json(view)
  })),
  http.post(EP.rules.testsApprove(':projectId'), route(async ({ request, params }) => {
    const { ids } = (await request.json()) as { ids: string[] }
    return json(ruleTests.approveTests(params.projectId as string, ids, demoUser.name))
  })),
  http.put(EP.rules.test(':projectId', ':ruleId'), route(async ({ request, params }) => {
    const view = ruleTests.editTest(params.projectId as string, params.ruleId as string, ((await request.json()) as { code: string }).code)
    return view ? json(view) : fail(404, 'no_test', `${params.ruleId as string} todavía no tiene prueba: genérala primero`)
  })),
  http.delete(EP.rules.test(':projectId', ':ruleId'), route(({ params }) => json(ruleTests.removeTest(params.projectId as string, params.ruleId as string)))),
  // Fase 5: matriz de permisos, evidencia de apoyo y prueba de fuerza (esta sigue en segundo plano)
  http.get(EP.rules.testMatrix(':projectId', ':ruleId'), route(({ params }) => json(ruleTests.getMatrix(params.projectId as string, params.ruleId as string)))),
  http.put(EP.rules.testMatrix(':projectId', ':ruleId'), route(async ({ request, params }) => {
    const { cells } = (await request.json()) as { cells: Record<string, Record<string, 'permitido' | 'prohibido' | null>> }
    const view = ruleTests.saveMatrix(params.projectId as string, params.ruleId as string, cells)
    return typeof view === 'string' ? fail(422, 'empty_matrix', view) : json(view)
  })),
  http.post(EP.rules.testEvidence(':projectId', ':ruleId'), route(({ params }) => json(ruleTests.explainRule(params.projectId as string, params.ruleId as string)))),
  http.post(EP.rules.testsStrength(':projectId'), route(async ({ request, params }) => {
    const { ids } = (await request.json()) as { ids: string[] | null }
    const view = ruleTests.strengthTests(params.projectId as string, ids)
    return typeof view === 'string' ? fail(409, 'nothing_to_test', view) : json(view)
  })),
  http.get(EP.rules.export(':projectId'), route(() => new HttpResponse(new Uint8Array([80, 75, 5, 6, ...new Array(18).fill(0)]), {
    headers: { 'Content-Type': 'application/zip', 'Content-Disposition': 'attachment; filename="reglas-api-pagos.zip"' },
  }))),

  // ─── Público ───
  http.get(EP.public.get(':shareId'), route(({ request, params }) => {
    const r = db.publicReport(params.shareId as string, param(request, 'token'))
    return r.ok ? json(r.data) : fail(r.status, r.code, r.message)
  })),
  http.post(EP.public.unlock(':shareId'), route(async ({ request, params }) => {
    const { password } = (await request.json()) as { password: string }
    const token = db.unlockShare(params.shareId as string, password)
    return token ? json({ token }) : fail(403, 'wrong_password', 'Contraseña incorrecta')
  })),

  // ─── Equipo ───
  http.get(EP.team.root, route(() => json(team.getTeam()))),
  http.patch(EP.team.root, route(async ({ request }) => json(team.rename(((await request.json()) as { name: string }).name)))),
  http.post(EP.team.invites, route(() => json(team.createInvite(window.location.origin)))),
  http.get(EP.team.invite(':code'), route(({ params }) => {
    const p = team.preview(params.code as string)
    return p ? json(p) : fail(404, 'not_found', 'Esta invitación no existe')
  })),
  http.post(EP.team.join, route(() => json(team.getTeam()))),
  http.post(EP.team.owner(':userId'), route(({ params }) => json(team.transfer(params.userId as string)))),
  http.delete(EP.team.member(':userId'), route(({ params }) => json(team.remove(params.userId === 'me' ? demoUser.id : (params.userId as string))))),
]
