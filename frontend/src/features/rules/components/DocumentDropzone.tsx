import { useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { Icon, Spinner } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import { DOCUMENT_EXTENSIONS } from '../utils/rules'

/**
 * Zona para subir el documento de requisitos: se arrastra o se elige con el explorador. Solo PDF y Word (.docx);
 * la validación del tipo la hace quien recibe el archivo (`onFile`), para que arrastrar y elegir den el mismo aviso.
 */
export function DocumentDropzone({ onFile, busy = false, label }: { onFile: (file: File) => void; busy?: boolean; label?: string }) {
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)

  const pick = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (file) onFile(file)
  }
  const drop = (e: DragEvent<HTMLElement>) => {
    e.preventDefault()
    setOver(false)
    const file = e.dataTransfer.files[0]
    if (file && !busy) onFile(file)
  }

  return (
    <button
      type="button"
      disabled={busy}
      onClick={() => input.current?.click()}
      onDragOver={(e) => {
        e.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={drop}
      className={cn(
        'w-full rounded-xl border-2 border-dashed px-4 py-5 text-center text-sm transition-colors disabled:opacity-60',
        over ? 'border-brand-500 bg-brand-50 dark:bg-brand-500/10' : 'border-slate-300 dark:border-slate-700 hover:border-brand-400 hover:bg-slate-50 dark:hover:bg-slate-800/40',
      )}
    >
      <span className="flex flex-col items-center gap-1.5 text-slate-600 dark:text-slate-300">
        {busy ? <Spinner className="w-5 h-5" /> : <Icon name="file" className="w-5 h-5 text-slate-400" />}
        <span className="font-medium">{label ?? 'Sube el documento de requisitos'}</span>
        <span className="text-xs text-slate-400">Arrástralo aquí o haz clic para elegirlo · PDF o Word (.docx)</span>
      </span>
      <input ref={input} type="file" accept={DOCUMENT_EXTENSIONS.join(',')} className="hidden" aria-label="Documento de requisitos" onChange={pick} />
    </button>
  )
}
