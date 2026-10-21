import { useMutation } from '@tanstack/react-query'
import { toast } from '@/shared/hooks/useToast'
import { authApi } from '../api/auth.api'

const KEY = 'iavoy-github-login'

interface PendingLogin {
  state: string
  /** Página a la que se vuelve después de iniciar sesión */
  returnTo: string
}

/** Lee y borra el inicio de sesión pendiente (un solo uso). */
export function takePendingLogin(): PendingLogin | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    sessionStorage.removeItem(KEY)
    return raw ? (JSON.parse(raw) as PendingLogin) : null
  } catch {
    return null
  }
}

/**
 * Manda al usuario a autorizar en GitHub. Guarda el `state` para comprobar al volver que el
 * callback corresponde a un login que inició esta pestaña (evita que alguien inyecte su propia cuenta).
 */
export function useGithubLogin(returnTo: string) {
  return useMutation({
    mutationFn: authApi.githubAuthorize,
    onSuccess: ({ url, state }) => {
      try {
        sessionStorage.setItem(KEY, JSON.stringify({ state, returnTo } satisfies PendingLogin))
      } catch {
        /* sin almacenamiento el callback no podrá validar el state y pedirá reintentar */
      }
      window.location.assign(url)
    },
    onError: (e) => toast(e.message || 'No se pudo iniciar sesión con GitHub', { tone: 'err' }),
  })
}
