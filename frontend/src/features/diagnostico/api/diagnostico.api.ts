import { useMutation } from '@tanstack/react-query'
import { EP } from '@/shared/api/endpoints'
import { http } from '@/shared/api/http'
import type { DiagnosticoRequest, DiagnosticoResponse } from '../types'

export const diagnosticoApi = {
  run: (body: DiagnosticoRequest) => http.post<DiagnosticoResponse>(EP.diagnostico, body),
}

export const useDiagnostico = () => useMutation({ mutationFn: diagnosticoApi.run })
