import { ApiError } from './errors'

const API_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

let getToken: () => string | null = () => null
let onUnauthorized: () => void = () => {}

/** La capa de auth registra aquí cómo obtener el token y qué hacer ante un 401. */
export function configureHttp(opts: { getToken: () => string | null; onUnauthorized: () => void }) {
  getToken = opts.getToken
  onUnauthorized = opts.onUnauthorized
}

export type Query = Record<string, string | number | boolean | undefined | null>

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  query?: Query
  /** Rutas públicas (vista compartida): no envían token ni cierran sesión ante 401 */
  anonymous?: boolean
}

function buildUrl(path: string, query?: Query) {
  const url = new URL(API_URL + path, window.location.origin)
  if (query) for (const [k, v] of Object.entries(query)) if (v != null) url.searchParams.set(k, String(v))
  return url.toString()
}

async function send(path: string, { body, query, headers, anonymous, ...init }: RequestOptions = {}): Promise<Response> {
  const token = anonymous ? null : getToken()
  const res = await fetch(buildUrl(path, query), {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(body !== undefined && { 'Content-Type': 'application/json' }),
      ...(token && { Authorization: `Bearer ${token}` }),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401 && !anonymous) onUnauthorized()
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new ApiError(res.status, data?.error?.code ?? 'http_error', data?.error?.message ?? res.statusText)
  }
  return res
}

export async function request<T>(path: string, opts?: RequestOptions): Promise<T> {
  const res = await send(path, opts)
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export interface SseEvent {
  event: string
  data: unknown
}

/**
 * POST que responde Server-Sent Events: llama a `onEvent` con cada evento conforme llega.
 * Los errores antes de empezar (401, 404, validación) llegan como ApiError, igual que en `request`.
 */
export async function postStream(path: string, body: unknown, onEvent: (e: SseEvent) => void): Promise<void> {
  const res = await send(path, { method: 'POST', body, headers: { Accept: 'text/event-stream' } })
  const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value.replace(/\r\n/g, '\n')
    let end: number
    while ((end = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, end)
      buffer = buffer.slice(end + 2)
      let event = 'message'
      const data: string[] = []
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
      }
      if (data.length) onEvent({ event, data: JSON.parse(data.join('\n')) })
    }
  }
}

/** Descarga un archivo (p. ej. la exportación del reporte) respetando el nombre que envía el servidor. */
export async function download(path: string, query: Query, fallbackName: string) {
  const res = await send(path, { method: 'GET', query, headers: { Accept: '*/*' } })
  const disposition = res.headers.get('Content-Disposition') ?? ''
  const name = /filename="?([^";]+)"?/.exec(disposition)?.[1] ?? fallbackName
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

export const http = {
  get: <T>(path: string, query?: Query, opts?: RequestOptions) => request<T>(path, { ...opts, method: 'GET', query }),
  post: <T>(path: string, body?: unknown, opts?: RequestOptions) => request<T>(path, { ...opts, method: 'POST', body }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PUT', body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
