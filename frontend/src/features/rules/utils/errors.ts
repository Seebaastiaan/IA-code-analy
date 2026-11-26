import { toast } from '@/shared/hooks/useToast'
import { ApiError } from '@/shared/api/errors'

/** Qué decir y qué ofrecer cuando falla algo que depende de la IA o del documento (en palabras, con la siguiente acción). */
const FRIENDLY: Record<string, { message: string; retry?: boolean }> = {
  llm_busy: { message: 'La IA está muy ocupada ahora. Espera unos segundos y reintenta.', retry: true },
  llm_rate_limited: { message: 'La IA llegó a su límite de uso. Espera un minuto y reintenta.', retry: true },
  llm_unavailable: { message: 'La IA no respondió. Reintenta; si sigue igual, avisa a quien administra la clave de IA.', retry: true },
  github_unavailable: { message: 'No pude leer el documento de GitHub. Reintenta en un momento.', retry: true },
  ai_fix_invalid: { message: 'La IA no logró una corrección válida esta vez. Reintenta.', retry: true },
  unsupported_type: { message: 'Ese tipo de archivo no sirve: sube un PDF o un Word (.docx).' },
  file_too_large: { message: 'El documento es demasiado grande: sube uno más pequeño o divídelo.' },
  invalid_document: { message: 'El archivo no llegó completo. Súbelo de nuevo.' },
}

/** El texto de un error de la API para una persona, y si tiene sentido ofrecer «Reintentar». */
export function friendlyError(error: Error): { message: string; retry: boolean } {
  const known = error instanceof ApiError ? FRIENDLY[error.code] : undefined
  if (known) return { message: known.message, retry: Boolean(known.retry) }
  const hint = error instanceof ApiError && error.code === 'no_rules_found' ? ' Prueba con otro archivo o escribe una regla con tus palabras.' : ''
  return { message: `${error.message}${hint}`, retry: false }
}

/** Avisa el error en palabras; con `retry` agrega el botón «Reintentar» cuando el fallo suele pasar solo. */
export function toastError(error: Error, retry?: () => void) {
  const { message, retry: canRetry } = friendlyError(error)
  toast(message, { tone: 'err', ms: canRetry && retry ? 10_000 : 6_000, action: canRetry && retry ? { label: 'Reintentar', onClick: retry } : undefined })
}
