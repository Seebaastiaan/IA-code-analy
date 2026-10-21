import { QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useSession } from '@/features/auth'
import { configureHttp } from '@/shared/api/http'
import { queryClient } from '@/shared/api/queryClient'
import { Toaster } from './layouts/Toaster'

// El cliente HTTP toma el token de la sesión; un 401 la cierra (el guard redirige a login)
configureHttp({
  getToken: () => useSession.getState().token,
  onUnauthorized: () => useSession.getState().signOut(),
})

export function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster />
    </QueryClientProvider>
  )
}
