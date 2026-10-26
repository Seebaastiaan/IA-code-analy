import { useCallback } from 'react'
import { useSearchParams } from 'react-router'

/** El hallazgo abierto en el drawer vive en ?finding=<id>, así se puede enlazar y el botón atrás lo cierra. */
export function useFindingParam() {
  const [params, setParams] = useSearchParams()
  const raw = params.get('finding')
  const findingId = raw ? Number(raw) : null

  const open = useCallback(
    (id: number) =>
      setParams((p) => {
        p.set('finding', String(id))
        return p
      }),
    [setParams],
  )
  const close = useCallback(
    () =>
      setParams(
        (p) => {
          p.delete('finding')
          return p
        },
        { replace: true },
      ),
    [setParams],
  )

  return { findingId, open, close }
}
