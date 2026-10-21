import { QueryClient } from '@tanstack/react-query'

/** Cliente único: lo usan los providers y los stores que invalidan datos fuera de React (p. ej. el job). */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
  },
})
