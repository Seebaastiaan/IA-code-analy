import { delay, http, HttpResponse, ws, type HttpResponseResolver, type PathParams } from 'msw'
import type { AnalyzeRequest } from '@/features/analysis/types'
import type { GithubCallbackRequest } from '@/features/auth/types'
import type { ProjectConfig } from '@/features/settings/types'
import { EP } from '@/shared/api/endpoints'
import * as db from '../db'
import * as github from '../github'
import * as team from '../team'
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

  // ─── Tablero y repositorios ───
  http.get(EP.dashboard, route(({ request }) => json(db.dashboard(param(request, 'repo'))))),
  http.get(EP.repos.list, route(() => json(db.listRepos()))),
  http.post(EP.repos.analyze(':repoId'), route(({ params }) => json({ job_id: db.reanalyze(params.repoId as string) }))),
  http.get(EP.repos.tree(':repoId'), route(({ params }) => json(db.tree(params.repoId as string)))),
  http.get(EP.file, route(({ request }) => {
    const path = param(request, 'path') ?? ''
    return json({ path, language: languageOf(path), content: db.getFile(param(request, 'repo') ?? '', path) })
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
    if (!/^https:\/\/(www\.)?github\.com\/[^/]+\/[^/]+/.test(body.url)) return fail(422, 'invalid_url', 'Usa la URL de un repositorio de GitHub (ej. https://github.com/equipo/proyecto)')
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

  // ─── Configuración ───
  http.get(EP.config(':projectId'), route(({ params }) => json(db.getConfig(params.projectId as string)))),
  http.put(EP.config(':projectId'), route(async ({ request, params }) => json(db.saveConfig(params.projectId as string, (await request.json()) as ProjectConfig)))),

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
