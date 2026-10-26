import { afterEach, describe, expect, it, vi } from 'vitest'
import { chatApi } from '@/features/assistant/api/chat.api'
import { ApiError } from '@/shared/api/errors'

/** Respuesta SSE cuyo cuerpo llega en los trozos indicados (cortados en cualquier lugar, como en la red). */
function sseResponse(chunks: string[], status = 200) {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) controller.enqueue(encoder.encode(c))
      controller.close()
    },
  })
  return new Response(body, { status, headers: { 'Content-Type': 'text/event-stream' } })
}

const BODY = { repo_id: 'r1', message: 'hola', history: [] }

describe('chatApi.askStream', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('entrega los trozos y devuelve la respuesta final', async () => {
    const done = { content: 'Hola mundo', sources: [{ file: 'a.py', line: 1 }], action: null, model: 'Gemini' }
    const raw = `event: delta\ndata: {"text": "Hola "}\n\nevent: delta\r\ndata: {"text": "mundo"}\r\n\r\nevent: done\ndata: ${JSON.stringify(done)}\n\n`
    // Cortes a mitad de evento y de línea
    vi.stubGlobal('fetch', vi.fn(async () => sseResponse([raw.slice(0, 10), raw.slice(10, 47), raw.slice(47)])))
    vi.stubGlobal('window', { location: { origin: 'http://localhost' } })
    const deltas: string[] = []
    const res = await chatApi.askStream(BODY, (t) => deltas.push(t))
    expect(deltas).toEqual(['Hola ', 'mundo'])
    expect(res).toEqual(done)
  })

  it('un evento error se vuelve ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => sseResponse(['event: error\ndata: {"code": "llm_busy", "message": "Saturado"}\n\n'])))
    vi.stubGlobal('window', { location: { origin: 'http://localhost' } })
    await expect(chatApi.askStream(BODY, () => {})).rejects.toMatchObject({ code: 'llm_busy', message: 'Saturado' })
  })

  it('si se corta sin done, falla', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => sseResponse(['event: delta\ndata: {"text": "Ho"}\n\n'])))
    vi.stubGlobal('window', { location: { origin: 'http://localhost' } })
    await expect(chatApi.askStream(BODY, () => {})).rejects.toBeInstanceOf(ApiError)
  })
})
