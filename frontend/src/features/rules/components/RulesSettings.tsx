import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from '@/shared/hooks/useToast'
import { Button, Card, Chip, ErrorState, Icon, PageLoader, Spinner } from '@/shared/ui'
import { projectRulesQuery, rulesApi, RULES_FILENAME, useProjectRules } from '../api/rules.api'
import type { ImportedRules, ProjectRules, RulesValidation } from '../types'
import { baseName, INVALID_DOCUMENT, isDocument, NO_AI_FOR_DOCUMENTS, saveText } from '../utils/rules'
import { useImportRules } from '../hooks/useImportRules'
import { AutoVerifyCard } from './AutoVerifyCard'
import { ConcordanceCard } from './ConcordanceCard'
import { DocumentDropzone } from './DocumentDropzone'
import { HarnessCard } from './HarnessCard'
import { ImportNotice } from './ImportNotice'
import { RuleTestsCard } from './RuleTestsCard'
import { WriteRuleCard } from './WriteRuleCard'
import { RulesApprovalTable } from './RulesApprovalTable'
import { ValidationResult } from './ValidationResult'

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
  if (data.active === 'app' && data.repo && !data.repo.valid)
    return (
      <p className="flex flex-wrap items-center gap-2">
        <Chip tone="brand">Corregidas en la app</Chip>
        <span className="text-sm text-slate-500">
          El <code className="font-mono">{data.repo.path}</code> del repositorio tiene errores: el análisis usa las reglas corregidas aquí. Descárgalas y súbelas al repositorio.
        </span>
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
      <span className="text-sm text-slate-500">{data.cloned ? 'El repositorio todavía no trae reglas: importa el documento de requisitos.' : 'Analiza el repositorio para saber si trae el archivo.'}</span>
    </p>
  )
}

function Editor({ repoId, data }: { repoId: string; data: ProjectRules }) {
  const queryClient = useQueryClient()
  const initial = data.uploaded?.content ?? data.repo?.content ?? ''
  const [text, setText] = useState(initial)
  const [result, setResult] = useState<RulesValidation | null>(null)
  const [notice, setNotice] = useState<ImportedRules | null>(null)
  const [reading, setReading] = useState<string | null>(null)
  // «Avanzado» (el archivo .toml): cerrado, salvo que haya un error que corregir. Se controla aquí para que no se cierre al escribir
  const [advanced, setAdvanced] = useState(false)
  // Reemplaza el contenido del editor: no se guarda hasta "Guardar en la app"
  const importRules = useImportRules((done) => {
    setText(done.content)
    setResult(done.validation)
    setNotice(done)
    if (!done.validation.valid) setAdvanced(true)
  })
  const fromDocument = (path: string) => {
    setReading(path)
    importRules.mutate({ request: { project_id: repoId, path } }, { onSettled: () => setReading(null) })
  }

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
    onError: (e) => {
      setResult({ valid: false, error: e.message, project: null, rules: [] })
      setAdvanced(true)
    },
  })
  const remove = useMutation({
    mutationFn: () => rulesApi.remove(repoId),
    onSuccess: (saved) => onSaved(saved, 'Se quitaron las reglas cargadas en la app'),
    onError: (e) => toast(e.message, { tone: 'err' }),
  })
  const template = useMutation({ mutationFn: () => rulesApi.template(repoId), onError: (e) => toast(e.message, { tone: 'err' }) })

  // Solo PDF o Word: la IA saca las reglas para que se revisen y aprueben aquí
  const upload = (file: File) => {
    if (!isDocument(file.name)) return toast(INVALID_DOCUMENT, { tone: 'err' })
    if (!data.can_import) return toast(NO_AI_FOR_DOCUMENTS, { tone: 'err' })
    setReading(file.name)
    importRules.mutate({ file, extra: { project_id: repoId } }, { onSettled: () => setReading(null) })
  }

  const dirty = Boolean(text.trim()) && text !== (data.uploaded?.content ?? data.repo?.content ?? '')
  const busy = validate.isPending || save.isPending || importRules.isPending
  // El archivo del repo es válido: gana a lo que se guarde aquí
  const fromRepo = data.active === 'repo' && Boolean(data.repo?.valid)
  // El archivo del repo tiene errores: lo que se guarde aquí se usa mientras siga así
  const repoInvalid = Boolean(data.repo && !data.repo.valid)

  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 className="font-semibold">{data.uploaded ? 'Reglas cargadas en la app' : 'Importar las reglas'}</h2>
      </div>
      {data.can_import && !fromRepo && data.documents.length > 0 && (
        <div className="mb-3 rounded-xl border border-slate-200 dark:border-slate-800 p-3.5 text-sm">
          <p className="text-slate-600 dark:text-slate-300">
            Encontré {data.documents.length === 1 ? 'un documento' : 'documentos'} de requisitos en el repositorio: la IA puede sacar las reglas para que las revises aquí.
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {data.documents.map((path) => (
              <Button key={path} variant="secondary" title={path} onClick={() => fromDocument(path)} disabled={importRules.isPending}>
                {reading === path ? <Spinner className="w-4 h-4" /> : <Icon name="wand" className="w-4 h-4" />}
                Sacar reglas de {baseName(path)}
              </Button>
            ))}
          </div>
        </div>
      )}
      {!fromRepo && (
        <div className="mb-3">
          <DocumentDropzone onFile={upload} busy={importRules.isPending} />
        </div>
      )}
      {reading && (
        <p className="mb-3 flex items-center gap-2 text-sm text-slate-500">
          <Spinner className="w-4 h-4" />
          Leyendo {reading} con IA… puede tardar hasta 30 segundos.
        </p>
      )}
      {notice && <ImportNotice imported={notice} />}
      {fromRepo && (
        <p className="mb-3 text-sm text-slate-500">
          El repositorio ya tiene <code className="font-mono">{data.repo?.path}</code> y es válido: el análisis usa ese archivo y lo que guardes aquí se ignora. Edítalo en el repositorio o desde el editor.
        </p>
      )}
      {repoInvalid && (
        <p className="mb-3 text-sm text-slate-500">
          {data.uploaded ? 'Estas son las reglas corregidas que usa el análisis' : 'Corrige aquí el archivo y guárdalo en la app: el análisis usará esta versión'} mientras{' '}
          <code className="font-mono">{data.repo?.path}</code> del repositorio siga con errores. Después descárgalo y súbelo al repositorio.
        </p>
      )}
      {dirty && !fromRepo && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-brand-50 dark:bg-brand-500/10 px-3.5 py-2.5 text-sm text-brand-800 dark:text-brand-200">
          <span>Las reglas nuevas todavía no están guardadas: guárdalas para revisarlas y aprobarlas en la tabla.</span>
          <Button onClick={() => save.mutate()} disabled={busy || result?.valid === false}>
            {save.isPending ? <Spinner className="w-4 h-4" /> : <Icon name="save" className="w-4 h-4" />}
            Guardar reglas
          </Button>
        </div>
      )}
      {result?.valid === false && <p className="mb-3 text-sm text-rose-600 dark:text-rose-400">Las reglas tienen un error: corrígelo en «Avanzado» para poder guardarlas.</p>}
      {/* El archivo .toml es un formato interno: queda en «Avanzado», cerrado salvo que haya un error que corregir */}
      <details open={advanced} onToggle={(e) => setAdvanced(e.currentTarget.open)} className="rounded-xl border border-slate-200 dark:border-slate-800 p-3.5">
        <summary className="cursor-pointer text-sm font-medium text-slate-600 dark:text-slate-300">Avanzado: archivo {RULES_FILENAME}, plantilla y patrones</summary>
        <div className="mt-3 mb-3 flex flex-wrap items-center gap-2">
          <Button variant="ghost" onClick={() => template.mutate()} disabled={template.isPending}>
            <Icon name="download" className="w-4 h-4" />
            Descargar plantilla
          </Button>
        </div>
      <textarea
        value={text}
        onChange={(e) => update(e.target.value)}
        spellCheck={false}
        aria-label="Texto de las reglas"
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
        <div className="mt-4">
          <RegexHelp />
        </div>
      </details>
    </Card>
  )
}

const STEPS = [
  { title: 'Importa el documento', text: 'Sube el PDF o Word de requisitos (o elige el que está en el repositorio): la IA saca las reglas.' },
  { title: 'Contesta las dudas y aprueba', text: 'Responde Sí o No a lo que el documento deja ambiguo y aprueba las reglas. Solo lo aprobado se verifica.' },
  { title: 'Pulsa «Preparar todo»', text: 'El programa prepara el entorno, escribe las pruebas y las corre. Puede tardar unos minutos.' },
  { title: 'Lee el resultado', text: 'Analiza el repositorio: el reporte dice qué reglas se cumplen y cuáles no.' },
]

function Steps() {
  return (
    <Card className="p-5">
      <h2 className="font-semibold mb-3">Cómo funciona</h2>
      <ol className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 text-sm text-slate-600 dark:text-slate-300">
        {STEPS.map((step, i) => (
          <li key={step.title} className="flex gap-2.5">
            <span className="w-5 h-5 shrink-0 rounded-full grid place-items-center text-[11px] font-bold bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300">{i + 1}</span>
            <span>
              <b className="block text-slate-800 dark:text-slate-100">{step.title}</b>
              {step.text}
            </span>
          </li>
        ))}
      </ol>
      <p className="mt-3 text-xs text-slate-400">Las reglas son de este proyecto. Si el repositorio ya tiene un archivo válido, gana el del repositorio.</p>
    </Card>
  )
}

/** Cómo escribir los patrones `prohibido` y `obligatorio` (expresiones regulares), con ejemplos que se pueden copiar. */
function RegexHelp() {
  const code = 'font-mono text-xs bg-slate-100 dark:bg-slate-800 rounded px-1 py-0.5'
  return (
    <Card className="p-5 h-fit">
      <h2 className="font-semibold mb-1">Cómo escribir un patrón (regex)</h2>
      <p className="text-sm text-slate-500 mb-3">
        <code className={code}>prohibido</code> es un texto que <b>no</b> debe aparecer en el código de la regla y <code className={code}>obligatorio</code> uno que <b>sí</b> debe aparecer. Se escriben como expresión regular.
      </p>
      <ul className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
        <li>
          <b>Texto tal cual:</b> <code className={code}>@requiere_admin</code> busca exactamente eso.
        </li>
        <li>
          <b>Los símbolos <code className={code}>{'. ( ) [ ] { } * + ? | ^ $'}</code> son especiales:</b> para buscarlos como texto ponles una barra antes. Para encontrar <code className={code}>float(</code> escribe <code className={code}>{'float\\('}</code>.
        </li>
        <li>
          <b>Cualquier carácter:</b> <code className={code}>{'.*'}</code>. Ejemplo: <code className={code}>{'descuento.*0\\.5'}</code>.
        </li>
        <li>
          <b>Uno u otro:</b> <code className={code}>{'md5|sha1'}</code>.
        </li>
        <li>
          <b>En el archivo .toml usa comillas simples</b> (<code className={code}>{"prohibido = 'float\\('"}</code>): así la barra no se duplica.
        </li>
      </ul>
      <p className="mt-3 text-xs text-slate-400">Pulsa «Validar»: si el patrón no es una expresión regular válida, te dice en qué regla está el error.</p>
    </Card>
  )
}

/** Configuración → Reglas de negocio (docs/PROPUESTA_REGLAS_NEGOCIO.md §6). */
export function RulesSettings({ repoId }: { repoId: string }) {
  const { data, error, refetch, isPlaceholderData } = useProjectRules(repoId)
  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />
  if (!data || isPlaceholderData) return <PageLoader />

  return (
    <div className="space-y-4">
      <Steps />
      <Card className="p-5">
        <h2 className="font-semibold mb-3">De dónde vienen las reglas</h2>
        <Origin data={data} />
        {data.repo && !data.repo.valid && (
          <p className="mt-3 text-sm text-rose-600 dark:text-rose-400 font-mono">
            {data.repo.path}: {data.repo.error}
          </p>
        )}
      </Card>
      {/* key: al guardar o quitar, el editor se reinicia con lo del servidor */}
      <Editor key={`${repoId}-${data.uploaded?.updated_at ?? 'none'}-${data.active}`} repoId={repoId} data={data} />
      <RulesApprovalTable repoId={repoId} data={data} />
      <AutoVerifyCard repoId={repoId} />
      <details className="rounded-2xl border border-slate-200 dark:border-slate-800 p-4">
        <summary className="cursor-pointer text-sm font-medium text-slate-600 dark:text-slate-300">
          Herramientas avanzadas: escribir una regla, arnés, pruebas una por una y comparación con lo que sabes
        </summary>
        <div className="mt-4 space-y-4">
          <WriteRuleCard repoId={repoId} canWrite={data.can_import} />
          <ConcordanceCard repoId={repoId} version={(data.active === 'repo' ? data.repo : data.uploaded)?.rules.map((r) => r.id).join(',') ?? ''} />
          <HarnessCard repoId={repoId} />
          <RuleTestsCard repoId={repoId} project={data.repo?.project ?? data.uploaded?.project ?? 'proyecto'} />
        </div>
      </details>
    </div>
  )
}
