import { useState, type FormEvent } from 'react'
import { Button, Card, Icon, Input, Label, Spinner } from '@/shared/ui'
import type { DiagnosticoRequest } from '../types'

interface DiagnosticoFormProps {
  busy: boolean
  onSubmit: (body: DiagnosticoRequest) => void
}

/** URL del repositorio, rama y (opcional) el archivo a diagnosticar. */
export function DiagnosticoForm({ busy, onSubmit }: DiagnosticoFormProps) {
  const [url, setUrl] = useState('')
  const [branch, setBranch] = useState('main')
  const [file, setFile] = useState('')

  const submit = (e: FormEvent) => {
    e.preventDefault()
    onSubmit({ url: url.trim(), branch: branch.trim() || 'main', file: file.trim() || null })
  }

  return (
    <form onSubmit={submit}>
      <Card className="p-5 sm:p-6 space-y-4">
        <div className="grid sm:grid-cols-3 gap-4">
          <div className="sm:col-span-2">
            <Label htmlFor="d-url">URL del repositorio</Label>
            <Input
              id="d-url"
              required
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/equipo/api-pagos"
              className="font-mono text-[13px]"
            />
          </div>
          <div>
            <Label htmlFor="d-branch">Rama</Label>
            <Input id="d-branch" value={branch} onChange={(e) => setBranch(e.target.value)} className="font-mono text-[13px]" />
          </div>
        </div>
        <div>
          <Label htmlFor="d-file">Archivo (opcional)</Label>
          <Input id="d-file" value={file} onChange={(e) => setFile(e.target.value)} placeholder="p. ej. app/servicios.py" className="font-mono text-[13px]" />
          <p className="text-xs text-slate-400 mt-1">Si lo dejas vacío se diagnostica el primer archivo .py que no sea de pruebas.</p>
        </div>
        <div className="flex justify-end pt-2 border-t border-slate-100 dark:border-slate-800">
          <Button type="submit" disabled={busy}>
            {busy ? <Spinner /> : <Icon name="sparkle" className="w-4 h-4" />}
            Diagnosticar con IA
          </Button>
        </div>
      </Card>
    </form>
  )
}
