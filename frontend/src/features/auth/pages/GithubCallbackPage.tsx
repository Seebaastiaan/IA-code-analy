import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { paths } from '@/shared/constants/paths'
import { toast } from '@/shared/hooks/useToast'
import { buttonClass, EmptyState, Spinner } from '@/shared/ui'
import { authApi } from '../api/auth.api'
import { takePendingLogin } from '../hooks/useGithubLogin'
import { useSession } from '../store/session.store'

/**
 * Redirect URI de la OAuth App. GitHub vuelve aquí con `code` y `state`; el backend valida el `state`,
 * canjea el `code`, crea o actualiza el usuario y devuelve la sesión. El token de GitHub nunca llega aquí.
 */
export default function GithubCallbackPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const signIn = useSession((s) => s.signIn)
  const [error, setError] = useState<string | null>(null)

  const exchange = useMutation({
    mutationFn: authApi.githubCallback,
    onError: (e) => setError(e.message),
  })

  // El code es de un solo uso: StrictMode monta dos veces y no debe canjearse dos veces
  const started = useRef(false)
  useEffect(() => {
    if (started.current) return
    started.current = true
    const pending = takePendingLogin()
    const code = params.get('code')
    const state = params.get('state')
    if (params.get('error') === 'access_denied') return setError('Cancelaste la autorización en GitHub.')
    if (!code || !state) return setError('GitHub no devolvió un código de autorización válido.')
    if (!pending || pending.state !== state) return setError('Este inicio de sesión no se inició desde esta pestaña o ya expiró.')
    exchange.mutate(
      { code, state },
      {
        onSuccess: ({ token, user }) => {
          queryClient.clear()
          signIn(token, user, true)
          toast(`Hola, ${user.name.split(' ')[0]}`)
          navigate(pending.returnTo, { replace: true })
        },
      },
    )
  }, [params, exchange, queryClient, signIn, navigate])

  return (
    <div className="min-h-screen grid place-items-center p-6">
      {error ? (
        <EmptyState icon="alert" title="No se pudo iniciar sesión con GitHub">
          <p>{error}</p>
          <Link to={paths.login()} className={buttonClass('primary', 'mt-3')}>
            Volver a intentarlo
          </Link>
        </EmptyState>
      ) : (
        <p className="flex items-center gap-3 text-sm text-slate-500">
          <Spinner className="w-5 h-5" />
          Iniciando sesión con GitHub…
        </p>
      )}
    </div>
  )
}
