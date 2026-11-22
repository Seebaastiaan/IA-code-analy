import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import type { PrepareStep, PrepareStatus, PrepareStepId } from '../types'
import { prepareQuery, rulesApi } from '../api/rules.api'

/** Los pasos técnicos que el programa hace solo (docs/PLAN_REGLAS_AUTOMATICO.md, pasos 1 y 2). Los dice el servidor. */
export type AutoStepId = PrepareStepId
export type AutoStatus = PrepareStatus
export type AutoStep = PrepareStep

const POLL_MS = 2000

/**
 * «Preparar todo»: el servidor encadena aprobar reglas, arnés, prueba de humo, pruebas, corrida, prueba de fuerza y
 * segunda opinión, y se detiene en el primer problema diciendo qué hacer. Corre aunque se cierre la pestaña: al volver,
 * la tarjeta muestra el avance o el resultado del último.
 */
export function useAutoVerify(repoId: string) {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const query = useQuery({
    ...prepareQuery(repoId),
    enabled: Boolean(repoId),
    refetchInterval: (q) => (q.state.data?.running ? POLL_MS : false),
  })
  const view = query.data
  const running = Boolean(view?.running)

  // Al terminar, lo demás de las reglas (tabla, arnés, pruebas) se vuelve a leer
  const wasRunning = useRef(false)
  useEffect(() => {
    if (wasRunning.current && !running) void queryClient.invalidateQueries({ queryKey: ['rules', repoId] })
    wasRunning.current = running
  }, [running, repoId, queryClient])

  const run = useCallback(async () => {
    setError(null)
    try {
      queryClient.setQueryData(prepareQuery(repoId).queryKey, await rulesApi.startPrepare(repoId))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo empezar')
    }
  }, [repoId, queryClient])

  const stop = useCallback(async () => {
    try {
      queryClient.setQueryData(prepareQuery(repoId).queryKey, await rulesApi.stopPrepare(repoId))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo detener')
    }
  }, [repoId, queryClient])

  const steps = view?.steps ?? []
  // Un error al lanzar (p. ej. ya estaba corriendo desde otra pestaña) se muestra en el primer paso
  const shown = error && steps.length ? steps.map((s, i) => (i === 0 ? { ...s, status: 'fallo' as const, note: error } : s)) : steps
  return { steps: shown, running, summary: view?.summary ?? null, run, stop }
}
