import { useQuery } from '@tanstack/react-query'
import { Suspense, useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router'
import { authApi, useSession } from '@/features/auth'
import { Spinner } from '@/shared/ui'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

/** Recupera el usuario cuando la sesión viene de un token guardado. */
function useCurrentUser() {
  const { user, setUser } = useSession()
  const { data } = useQuery({ queryKey: ['me'], queryFn: authApi.me, enabled: !user })
  useEffect(() => {
    if (data) setUser(data)
  }, [data, setUser])
}

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false)
  const { pathname } = useLocation()
  useCurrentUser()

  // Al cambiar de página se vuelve arriba (el menú móvil se cierra desde el propio enlace)
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return (
    <div>
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="lg:pl-64 min-h-screen flex flex-col">
        <TopBar onOpenMenu={() => setMenuOpen(true)} />
        <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
          <Suspense
            fallback={
              <div className="grid place-items-center py-24 text-slate-400">
                <Spinner className="w-6 h-6" />
              </div>
            }
          >
            <div key={pathname} className="animate-fade-in">
              <Outlet />
            </div>
          </Suspense>
        </main>
      </div>
    </div>
  )
}
