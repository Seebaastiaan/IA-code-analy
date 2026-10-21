import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router'
import { Providers } from '@/app/providers'
import { router } from '@/app/router/routes'
import '@/styles/globals.css'

/** Con VITE_USE_MOCKS=true las llamadas a /api se responden con MSW (sin backend). */
async function enableMocks() {
  if (import.meta.env.VITE_USE_MOCKS !== 'true') return
  const { worker } = await import('@/mocks/browser')
  await worker.start({ onUnhandledRequest: 'bypass' })

  // Desarrollo: entra directo con la cuenta de prueba para poder abrir cualquier ruta.
  // Solo existe dentro del modo mock, así que nunca se salta la autenticación de un backend real.
  if (import.meta.env.VITE_AUTO_LOGIN === 'true') {
    const { useSession } = await import('@/features/auth')
    const { demoUser } = await import('@/mocks/fixtures/user')
    if (!useSession.getState().token) useSession.getState().signIn('mock-token', demoUser, false)
  }
}

enableMocks().then(() => {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <Providers>
        <RouterProvider router={router} />
      </Providers>
    </StrictMode>,
  )
})
