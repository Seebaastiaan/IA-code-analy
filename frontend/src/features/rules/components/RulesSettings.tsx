import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRef, useState, type ChangeEvent } from 'react'
import { toast } from '@/shared/hooks/useToast'
import { Button, Card, Chip, ErrorState, Icon, PageLoader, SeverityBadge, Spinner } from '@/shared/ui'
import { projectRulesQuery, rulesApi, RULES_FILENAME, useProjectRules } from '../api/rules.api'
import type { ProjectRules, RulesValidation } from '../types'
import { saveText } from '../utils/rules'

const MAX_BYTES = 256 * 1024

function Origin({ data }: { data: ProjectRules }) {
  if (data.active === 'repo' && data.repo)
    return (
      <p className="flex flex-wrap items-center gap-2">
        <Chip tone="success">
          <Icon name="branch" className="w-3 h-3" />
          Repositorio
        </Chip>
        <code className="font-mono text-sm">{data.repo.path}</code>
        {data.commit && <span className="text-xs text-slate-400 font-mono">commit {data.commit.slice(0, 7)}</span>}
      </p>
    )
  if (data.active === 'app')
    return (
      <p className="flex flex-wrap items-center gap-2">
        <Chip tone="brand">Cargadas en la app</Chip>
        <span className="text-sm text-slate-500">No están en el repositorio: descárgalas y súbelas con un commit para que cuenten como entregable.</span>
      </p>
    )
  return (
    <p className="flex flex-wrap items-center gap-2">
      <Chip>Sin reglas</Chip>
      <span className="text-sm text-slate-500">{data.cloned ? `El repositorio no tiene ${RULES_FILENAME}.` : 'Analiza el repositorio para saber si trae el archivo.'}</span>
    </p>
  )
}

function ValidationResult({ result }: { result: RulesValidation }) {
  if (!result.valid)
    return (
      <p role="alert" className="mt-3 rounded-xl bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-300 px-3.5 py-2.5 text-sm font-mono">
        {result.error}
      </p>
    )
  return (
    <div className="mt-3 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 px-3.5 py-2.5 text-sm" role="status">
      <p className="font-medium text-emerald-700 dark:text-emerald-300">
        Válido · {result.project} · {result.rules.length} regla(s)
      </p>
      {result.rules.length > 0 && (
        <ul className="mt-2 space-y-1">
          {result.rules.map((r) => (
            <li key={r.id} className="flex items-center gap-2 min-w-0">
              <span className="font-mono text-xs text-slate-500 shrink-0">{r.id}</span>
              <SeverityBadge sev={r.severity} />
              <span className="truncate">{r.title}</span>
              <span className="ml-auto shrink-0 text-xs text-slate-400">{r.pattern ? 'patrón' : 'pruebas'}</span>
            </li>
          ))}
        </ul>
      )}
      {result.warnings?.map((w) => (
        <p key={w} className="mt-2 text-amber-700 dark:text-amber-300 font-mono text-xs">
          Aviso: {w}
        </p>
      ))}
    </div>
  )
}

function Editor({ repoId, data }: { repoId: string; data: ProjectRules }) {
  const queryClient = useQueryClient()
  const initial = data.uploaded?.content ?? data.repo?.content ?? ''
  const [text, setText] = useState(initial)
  const [result, setResult] = useState<RulesValidation | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const update = (next: string) => {
    setText(next)
    setResult(null)
  }
  const onSaved = (saved: ProjectRules, message: string) => {
    queryClient.setQueryData(projectRulesQuery(repoId).queryKey, saved)
    toast(message)
  }

  const validate = useMutation({ mutationFn: () => rulesApi.validate(repoId, text), onSuccess: setResult, onError: (e) => toast(e.message, { tone: 'err' }) })
  const save = useMutation({
    mutationFn: () => rulesApi.upload(repoId, text),
    onSuccess: (saved) => {
      setResult(saved.uploaded)
      onSaved(saved, saved.active === 'repo' ? 'Guardadas en la app (el análisis usa las del repositorio)' : 'Reglas guardadas: se usarán en el siguiente análisis')
    },
    // 422 invalid_rules: el mensaje trae la línea del error
    onError: (e) => setResult({ valid: false, error: e.message, project: null, rules: [] }),
  })
  const remove = useMutation({
    mutationFn: () => rulesApi.remove(repoId),
    onSuccess: (saved) => onSaved(saved, 'Se quitaron las reglas cargadas en la app'),
    onError: (e) => toast(e.message, { tone: 'err' }),
  })
  const template = useMutation({ mutationFn: () => rulesApi.template(repoId), onError: (e) => toast(e.message, { tone: 'err' }) })

  const upload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (file.size > MAX_BYTES) {
      toast(`El archivo pesa más de ${MAX_BYTES / 1024} KB`, { tone: 'err' })
      return
    }
    update(await file.text())
  }

  const busy = validate.isPending || save.isPending
  const fromRepo = data.active === 'repo'

  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 className="font-semibold">{fromRepo && !data.uploaded ? `Contenido de ${data.repo?.path}` : 'Reglas cargadas en la app'}</h2>
        <div className="flex flex-wrap gap-1">
          <Button variant="ghost" onClick={() => template.mutate()} disabled={template.isPending}>
            <Icon name="download" className="w-4 h-4" />
            Descargar plantilla
          </Button>
          <Button variant="ghost" onClick={() => fileInput.current?.click()}>
            <Icon name="file" className="w-4 h-4" />
            Subir archivo
          </Button>
          <input ref={fileInput} type="file" accept=".toml,text/plain" className="hidden" aria-label="Archivo de reglas" onChange={(e) => void upload(e)} />
        </div>
      </div>
      {fromRepo && (
        <p className="mb-3 text-sm text-slate-500">
          El repositorio ya tiene <code className="font-mono">{data.repo?.path}</code>: el análisis usa ese archivo y lo que guardes aquí se ignora. Edítalo en el repositorio o desde el editor.
        </p>
      )}
      <textarea
        value={text}
        onChange={(e) => update(e.target.value)}
        spellCheck={false}
        aria-label="Contenido de reglas_negocio.toml"
        placeholder={'[proyecto]\nnombre = "Mi proyecto"\n\n[[regla]]\nid = "RN-001"\n…'}
        className="w-full min-h-80 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-950 text-slate-100 font-mono text-xs leading-relaxed p-4 outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15"
      />
      {result && <ValidationResult result={result} />}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="secondary" onClick={() => validate.mutate()} disabled={!text.trim() || busy}>
          {validate.isPending ? <Spinner className="w-4 h-4" /> : <Icon name="check" className="w-4 h-4" />}
          Validar
        </Button>
        <Button onClick={() => save.mutate()} disabled={!text.trim() || busy || text === data.uploaded?.content}>
          {save.isPending ? <Spinner className="w-4 h-4" /> : <Icon name="save" className="w-4 h-4" />}
          Guardar en la app
        </Button>
        <Button variant="secondary" onClick={() => saveText(RULES_FILENAME, text)} disabled={!text.trim()}>
          <Icon name="download" className="w-4 h-4" />
          Descargar para el repo
        </Button>
        {data.uploaded && (
          <Button variant="ghost" className="text-rose-600 dark:text-rose-400" onClick={() => remove.mutate()} disabled={remove.isPending}>
            Quitar de la app
          </Button>
        )}
      </div>
    </Card>
  )
}

const STEPS = [
  'Descarga la plantilla (o escribe las reglas aquí).',
  'Escribe las reglas del negocio: salen de los requerimientos y criterios de aceptación.',
  'Por cada regla, una prueba con @pytest.mark.regla("RN-###") (o llamada test_rn###_…) o un patrón prohibido / obligatorio.',
  'Haz commit de reglas_negocio.toml y las pruebas en la raíz del repositorio.',
  'Analiza: el paso 10 dice qué reglas cumplen, cuáles no y cuáles no tienen prueba.',
]

/** Configuración → Reglas de negocio (docs/PROPUESTA_REGLAS_NEGOCIO.md §6). */
export function RulesSettings({ repoId }: { repoId: string }) {
  const { data, error, refetch, isPlaceholderData } = useProjectRules(repoId)
  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />
  if (!data || isPlaceholderData) return <PageLoader />

  return (
    <div className="grid lg:grid-cols-3 gap-4">
      <div className="lg:col-span-2 space-y-4">
        <Card className="p-5">
          <h2 className="font-semibold mb-3">Origen de las reglas</h2>
          <Origin data={data} />
          {data.repo && !data.repo.valid && (
            <p className="mt-3 text-sm text-rose-600 dark:text-rose-400 font-mono">
              {data.repo.path}: {data.repo.error}
            </p>
          )}
        </Card>
        {/* key: al guardar o quitar, el editor se reinicia con lo del servidor */}
        <Editor key={`${repoId}-${data.uploaded?.updated_at ?? 'none'}-${data.active}`} repoId={repoId} data={data} />
      </div>
      <Card className="p-5 h-fit">
        <h2 className="font-semibold mb-3">Cómo se verifican</h2>
        <ol className="space-y-2.5 text-sm text-slate-600 dark:text-slate-300">
          {STEPS.map((s, i) => (
            <li key={s} className="flex gap-2.5">
              <span className="w-5 h-5 shrink-0 rounded-full grid place-items-center text-[11px] font-bold bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300">{i + 1}</span>
              <span>{s}</span>
            </li>
          ))}
        </ol>
        <p className="mt-4 text-xs text-slate-400">
          Las reglas son de este proyecto: no se comparten con otros repositorios. Si el repositorio tiene el archivo, gana el del repositorio. Las reglas todavía no cuentan en el score.
        </p>
      </Card>
    </div>
  )
}
