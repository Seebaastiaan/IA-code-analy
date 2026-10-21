import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { authApi, useSession } from '@/features/auth'
import { paths } from '@/shared/constants/paths'

export function UserMenu() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user, signOut } = useSession()

  // Cierra al hacer clic fuera
  useEffect(() => {
    if (!open) return
    const onClick = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('click', onClick)
    return () => document.removeEventListener('click', onClick)
  }, [open])

  const logout = async () => {
    setOpen(false)
    await authApi.logout().catch(() => {})
    signOut()
    queryClient.clear()
    navigate(paths.login(), { replace: true })
  }

  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => setOpen((o) => !o)} className="flex items-center gap-2 p-1 pr-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800">
        {user?.avatar_url ? (
          <img src={user.avatar_url} alt="" className="w-8 h-8 rounded-lg" />
        ) : (
          <span className="w-8 h-8 rounded-lg bg-gradient-to-br from-sky-400 to-brand-500 text-white text-xs font-bold grid place-items-center">{user?.initials ?? '··'}</span>
        )}
        <span className="hidden sm:block text-sm font-medium">{user?.name ?? ''}</span>
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-56 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl p-1.5 animate-fade-in">
          <div className="px-3 py-2 border-b border-slate-100 dark:border-slate-800 mb-1">
            <p className="text-sm font-semibold">{user?.name}</p>
            {user?.login && <p className="text-xs text-slate-500">@{user.login}</p>}
            {user && <p className="text-xs text-slate-500">{`${user.team.name} · ${user.team.members} miembro(s)`}</p>}
          </div>
          <button type="button" onClick={logout} className="w-full text-left px-3 py-2 rounded-lg text-sm text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-500/10">
            Cerrar sesión
          </button>
        </div>
      )}
    </div>
  )
}
