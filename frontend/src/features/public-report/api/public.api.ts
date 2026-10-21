import { EP } from '@/shared/api/endpoints'
import { http } from '@/shared/api/http'
import type { PublicReport, UnlockResponse } from '../types'

/** Rutas públicas: no envían el token de sesión. */
export const publicApi = {
  get: (shareId: string, token: string | null) => http.get<PublicReport>(EP.public.get(shareId), { token }, { anonymous: true }),
  unlock: (shareId: string, password: string) => http.post<UnlockResponse>(EP.public.unlock(shareId), { password }, { anonymous: true }),
}
