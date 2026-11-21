import { useMutation } from '@tanstack/react-query'
import { toast } from '@/shared/hooks/useToast'
import { rulesApi } from '../api/rules.api'
import type { ImportedRules, ImportRulesRequest } from '../types'
import { fileToBase64, isDocument, MAX_DOCUMENT_BYTES } from '../utils/rules'

export type ImportInput = { request: ImportRulesRequest } | { file: File; extra: ImportRulesRequest }

/**
 * La IA saca las reglas de un documento de requisitos: desde una ruta del repo (`request`) o un archivo subido
 * (`file`; `extra` lleva la url del repo o el project_id para el nombre del proyecto). No guarda nada.
 */
export function useImportRules(onImported: (imported: ImportedRules) => void) {
  return useMutation({
    mutationFn: async (input: ImportInput) => {
      if ('request' in input) return rulesApi.importDocument(input.request)
      const { file, extra } = input
      if (!isDocument(file.name)) throw new Error('Usa un PDF, Word (.docx), Markdown (.md) o texto (.txt)')
      if (file.size > MAX_DOCUMENT_BYTES) throw new Error(`El documento pesa más de ${MAX_DOCUMENT_BYTES / (1024 * 1024)} MB`)
      return rulesApi.importDocument({ ...extra, filename: file.name, data: await fileToBase64(file) })
    },
    onSuccess: onImported,
    onError: (e) => toast(e.message, { tone: 'err' }),
  })
}
