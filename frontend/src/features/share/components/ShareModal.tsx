import { useMutation } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { exportReport } from '@/features/report/api/report.api'
import type { ExportFormat } from '@/features/report/types'
import { paths } from '@/shared/constants/paths'
import { toast } from '@/shared/hooks/useToast'
import { Button, Icon, Input, Label, Modal, Select, Spinner, Toggle, buttonClass } from '@/shared/ui'
import { shareApi } from '../api/share.api'
import type { ExpiryDays, ShareResponse } from '../types'

const EXPIRY: { value: ExpiryDays; label: string }[] = [
  { value: 1, label: '1 día' },
  { value: 7, label: '7 días' },
  { value: 30, label: '30 días' },
  { value: 0, label: 'Nunca' },
]

const FORMATS: { value: ExportFormat; label: string }[] = [
  { value: 'json', label: 'JSON' },
  { value: 'html', label: 'HTML' },
  { value: 'md', label: 'Markdown' },
  { value: 'sarif', label: 'SARIF' },
]

function Row({ title, desc, children }: { title: string; desc: string; children: ReactNode }) {
  return (
    <div className="p-4 flex items-center gap-3">
      <div className="flex-1">
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-slate-500">{desc}</p>
      </div>
      {children}
    </div>
  )
}

interface ShareModalProps {
  reportId: string
  title: string
  onClose: () => void
}

export function ShareModal({ reportId, title, onClose }: ShareModalProps) {
  const [protect, setProtect] = useState(false)
  const [password, setPassword] = useState('')
  const [days, setDays] = useState<ExpiryDays>(7)
  const [includeCode, setIncludeCode] = useState(false)
  const [link, setLink] = useState<ShareResponse | null>(null)
  const [exporting, setExporting] = useState<ExportFormat | null>(null)

  const create = useMutation({
    mutationFn: () => shareApi.create(reportId, { password: protect ? password : null, expires_days: days, include_code: includeCode }),
    onSuccess: (res) => {
      setLink(res)
      toast(`Enlace creado. ${days ? `Expira en ${days} día(s)` : 'No expira'}`)
    },
    onError: (e) => toast(e.message, { tone: 'err' }),
  })

  // Cambiar una opción invalida el enlace ya creado: hay que generarlo de nuevo
  const change = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v)
    setLink(null)
  }

  const copy = async () => {
    if (!link) return
    try {
      await navigator.clipboard.writeText(link.url)
      toast('Enlace copiado al portapapeles')
    } catch {
      toast(`Enlace: ${link.url}`, { tone: 'info' })
    }
  }

  const doExport = async (format: ExportFormat) => {
    setExporting(format)
    try {
      await exportReport(reportId, format)
    } catch (e) {
      toast(e instanceof Error ? e.message : 'No se pudo exportar', { tone: 'err' })
    } finally {
      setExporting(null)
    }
  }

  return (
    <Modal onClose={onClose}>
      <div className="p-5 sm:p-6 border-b border-slate-200 dark:border-slate-800 flex items-start gap-3">
        <span className="w-10 h-10 rounded-xl bg-brand-100 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300 grid place-items-center">
          <Icon name="share" />
        </span>
        <div className="flex-1">
          <h3 className="text-lg font-semibold">Compartir reporte</h3>
          <p className="text-sm text-slate-500 dark:text-slate-400">{title}</p>
        </div>
        <button type="button" onClick={onClose} aria-label="Cerrar" className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400">
          <Icon name="x" />
        </button>
      </div>

      <div className="p-5 sm:p-6 space-y-5">
        <div>
          <Label htmlFor="share-url">Enlace público</Label>
          <div className="flex gap-2">
            <Input id="share-url" readOnly value={link?.url ?? ''} placeholder="Configura las opciones y crea el enlace" className="font-mono text-xs" />
            <Button variant="secondary" className="shrink-0 px-3" onClick={copy} disabled={!link}>
              <Icon name="copy" className="w-4 h-4" />
              <span className="hidden sm:inline">Copiar</span>
            </Button>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 dark:border-slate-800 divide-y divide-slate-200 dark:divide-slate-800">
          <Row title="Proteger con contraseña" desc="Quien abra el enlace deberá escribirla">
            <Toggle label="Proteger con contraseña" checked={protect} onChange={change(setProtect)} />
          </Row>
          {protect && (
            <div className="p-4">
              <Input type="password" value={password} onChange={(e) => change(setPassword)(e.target.value)} placeholder="Contraseña del enlace" aria-label="Contraseña del enlace" />
            </div>
          )}
          <Row title="Expiración" desc="El enlace deja de funcionar después">
            <Select value={days} onChange={(e) => change(setDays)(Number(e.target.value) as ExpiryDays)} className="w-auto" aria-label="Expiración">
              {EXPIRY.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          </Row>
          <Row title="Incluir fragmentos de código" desc="Por defecto solo se comparten hallazgos">
            <Toggle label="Incluir fragmentos de código" checked={includeCode} onChange={change(setIncludeCode)} />
          </Row>
        </div>

        <div>
          <p className="block text-sm font-medium mb-1.5 text-slate-700 dark:text-slate-300">Exportar</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {FORMATS.map((f) => (
              <Button key={f.value} variant="secondary" className="px-2" onClick={() => void doExport(f.value)} disabled={exporting !== null}>
                {exporting === f.value ? <Spinner /> : <Icon name="download" className="w-4 h-4" />}
                {f.label}
              </Button>
            ))}
          </div>
        </div>
      </div>

      <div className="p-5 sm:p-6 pt-0 flex flex-col-reverse sm:flex-row gap-2 sm:justify-end">
        {link && (
          <Link to={paths.publicReport(link.share_id)} className={buttonClass('secondary')}>
            <Icon name="eye" className="w-4 h-4" />
            Ver como invitado
          </Link>
        )}
        <Button onClick={() => create.mutate()} disabled={create.isPending || (protect && !password) || Boolean(link)}>
          {create.isPending && <Spinner />}
          {link ? 'Enlace creado' : 'Crear enlace'}
        </Button>
      </div>
    </Modal>
  )
}
