import { useQuery } from '@tanstack/react-query'
import { EP } from '@/shared/api/endpoints'
import { ApiError } from '@/shared/api/errors'
import { http, postStream } from '@/shared/api/http'
import type { ChatRequest, ChatResponse, IndexInfo } from '../types'

export const chatApi = {
  ask: (body: ChatRequest) => http.post<ChatResponse>(EP.chat, body),
  /** Igual que `ask`, pero por SSE: `onDelta` recibe la respuesta mientras se genera. */
  askStream: async (body: ChatRequest, onDelta: (text: string) => void): Promise<ChatResponse> => {
    let final: ChatResponse | null = null
    await postStream(EP.chatStream, body, ({ event, data }) => {
      if (event === 'delta') onDelta((data as { text: string }).text)
      else if (event === 'done') final = data as ChatResponse
      else if (event === 'error') {
        const { code, message } = data as { code: string; message: string }
        throw new ApiError(503, code, message)
      }
    })
    if (!final) throw new ApiError(502, 'stream_cut', 'La respuesta se cortó antes de terminar. Intenta de nuevo.')
    return final
  },
  index: (repoId: string) => http.get<IndexInfo>(EP.repos.index(repoId)),
}

// La primera vez el backend indexa en segundo plano: se consulta hasta que termine
export const useIndexInfo = (repoId: string) =>
  useQuery({
    queryKey: ['index', repoId],
    queryFn: () => chatApi.index(repoId),
    // building: se consulta seguido; error: el servidor reintenta la indexación pasado un minuto
    refetchInterval: (q) => (q.state.data?.status === 'building' ? 2000 : q.state.data?.status === 'error' ? 60_000 : false),
  })
