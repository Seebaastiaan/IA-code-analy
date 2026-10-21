/**
 * GitHub simulado. El login con GitHub sale de la app y regresa recargando la página, así que el
 * `state` pendiente vive en sessionStorage (el resto de mocks/db.ts se reinicia al recargar).
 */
import type { GithubBranch, GithubRepo, GithubStatus } from '@/features/github/types'
import { paths } from '@/shared/constants/paths'
import { demoUser } from './fixtures/user'

const KEY = 'iavoy-mock-oauth-state'

/** En real el backend arma la URL de github.com/login/oauth/authorize; aquí se salta GitHub y vuelve directo. */
export function authorize() {
  const state = Math.random().toString(16).slice(2, 12)
  try {
    sessionStorage.setItem(KEY, state)
  } catch {
    /* sin almacenamiento el callback rechazará el state */
  }
  return { url: `${window.location.origin}${paths.githubCallback()}?code=mock-code&state=${state}`, state }
}

/** true si el state es el que emitió `authorize` (se consume). */
export function consumeState(state: string) {
  try {
    const pending = sessionStorage.getItem(KEY)
    sessionStorage.removeItem(KEY)
    return pending !== null && pending === state
  } catch {
    return false
  }
}

export function status(): GithubStatus {
  return { connected: true, login: demoUser.login ?? null, avatar_url: demoUser.avatar_url ?? null }
}

const ago = (days: number) => new Date(Date.now() - days * 86_400_000).toISOString()

const REPOS: GithubRepo[] = [
  { full_name: 'equipo/api-pagos', html_url: 'https://github.com/equipo/api-pagos', default_branch: 'main', private: true, description: 'API de cobros con Stripe y FastAPI', pushed_at: ago(0.1) },
  { full_name: 'equipo/etl-ventas', html_url: 'https://github.com/equipo/etl-ventas', default_branch: 'develop', private: true, description: 'ETL diario de ventas a BigQuery', pushed_at: ago(1) },
  { full_name: 'equipo/bot-soporte', html_url: 'https://github.com/equipo/bot-soporte', default_branch: 'main', private: false, description: 'Bot de soporte para Slack', pushed_at: ago(3) },
  { full_name: 'ana-lopez/scraper-precios', html_url: 'https://github.com/ana-lopez/scraper-precios', default_branch: 'main', private: false, description: null, pushed_at: ago(12) },
  { full_name: 'ana-lopez/dotfiles', html_url: 'https://github.com/ana-lopez/dotfiles', default_branch: 'master', private: false, description: 'Configuración personal', pushed_at: ago(40) },
]

const BRANCHES: Record<string, string[]> = {
  'equipo/api-pagos': ['main', 'develop', 'feature/reembolsos', 'fix/webhook-timeout'],
  'equipo/etl-ventas': ['develop', 'main'],
}

export function repos(q: string | null): GithubRepo[] {
  const term = q?.toLowerCase() ?? ''
  return REPOS.filter((r) => r.full_name.toLowerCase().includes(term))
}

export function branches(fullName: string): GithubBranch[] | null {
  const repo = REPOS.find((r) => r.full_name === fullName)
  if (!repo) return null
  return (BRANCHES[fullName] ?? [repo.default_branch]).map((name) => ({ name }))
}
