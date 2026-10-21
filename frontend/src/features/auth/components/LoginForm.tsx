import { useLocation } from 'react-router'
import { paths } from '@/shared/constants/paths'
import { Button, Spinner } from '@/shared/ui'
import { useGithubLogin } from '../hooks/useGithubLogin'

export function GithubMark({ className = 'w-5 h-5' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true" className={className}>
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  )
}

export function LoginForm() {
  const location = useLocation()
  // Vuelve a la página que pidió login, o al tablero
  const login = useGithubLogin((location.state as { from?: string } | null)?.from ?? paths.dashboard())
  const busy = login.isPending || login.isSuccess

  return (
    <div className="w-full max-w-sm animate-fade-in">
      <div className="lg:hidden flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-fuchsia-500 text-white grid place-items-center font-extrabold text-sm">IA</div>
        <span className="text-xl font-bold">IA voy</span>
      </div>
      <h1 className="text-2xl font-bold tracking-tight">Inicia sesión</h1>
      <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 mb-8">Entra con tu cuenta de GitHub para analizar tus repositorios, incluidos los privados.</p>
      <Button
        onClick={() => login.mutate()}
        disabled={busy}
        className="w-full py-3 bg-slate-900 hover:bg-slate-800 active:bg-slate-950 shadow-slate-900/20 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-100"
      >
        {busy ? <Spinner /> : <GithubMark />}
        Continuar con GitHub
      </Button>
      <p className="mt-4 text-xs text-slate-400">Si ya tienes la sesión de GitHub abierta en este navegador, solo tendrás que autorizar a IA voy la primera vez.</p>
    </div>
  )
}
