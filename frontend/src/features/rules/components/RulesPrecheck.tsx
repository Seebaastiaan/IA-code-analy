import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { toast } from '@/shared/hooks/useToast'
import { Button, Icon, Modal, Spinner, type IconName } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import { rulesApi, RULES_FILENAME } from '../api/rules.api'
import type { ImportedRules, RulesValidation } from '../types'
import { githubRepo, INVALID_DOCUMENT, isDocument, NO_AI_FOR_DOCUMENTS, precheckView, saveText, type PrecheckTone } from '../utils/rules'
import { useImportRules } from '../hooks/useImportRules'
import { DocumentDropzone } from './DocumentDropzone'
import { ImportNotice } from './ImportNotice'
import { ValidationResult } from './ValidationResult'

/** Reglas escritas o corregidas en el formulario (ya validadas): viajan con el análisis. */
export interface FormRules {
  text: string
  validation: RulesValidation
}

// Espera a que el usuario deje de escribir la URL antes de consultar GitHub
const DEBOUNCE_MS = 500

const TONE: Record<PrecheckTone, { box: string; icon: IconName; iconClass: string }> = {
  ok: { box: 'border-emerald-200 bg-emerald-50/60 dark:border-emerald-500/20 dark:bg-emerald-500/5', icon: 'check', iconClass: 'text-emerald-600 dark:text-emerald-400' },
  warn: { box: 'border-amber-200 bg-amber-50/60 dark:border-amber-500/20 dark:bg-amber-500/5', icon: 'alert', iconClass: 'text-amber-600 dark:text-amber-400' },
  error: { box: 'border-rose-200 bg-rose-50/60 dark:border-rose-500/20 dark:bg-rose-500/5', icon: 'alert', iconClass: 'text-rose-600 dark:text-rose-400' },
  neutral: { box: 'border-slate-200 dark:border-slate-800', icon: 'doc', iconClass: 'text-slate-400' },
}

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(id)
  }, [value, ms])
  return debounced
}

function RulesModal({ url, branch, initial, title, canImport, imported, onUse, onClose }: {
  url: string
  branch: string
  initial: string
  title: string
  /** Hay IA para sacar las reglas de un PDF, Word o Markdown subido */
  canImport: boolean
  /** El contenido inicial lo propuso la IA desde un documento */
  imported?: ImportedRules
  onUse: (rules: FormRules) => void
  onClose: () => void
}) {
  const [text, setText] = useState(initial)
  const [result, setResult] = useState<RulesValidation | null>(imported?.validation ?? null)
  const [notice, setNotice] = useState<ImportedRules | null>(imported ?? null)
  const importRules = useImportRules((done) => {
    setText(done.content)
    setResult(done.validation)
    setNotice(done)
  })
  // El backend valida con el parser real y revisa `rutas` contra el árbol de la rama
  const check = useMutation({
    mutationFn: async (content: string) => (await rulesApi.precheck(url, branch, content)).checked!,
    onError: (e) => toast(e.message, { tone: 'err' }),
  })

  const update = (next: string) => {
    setText(next)
    setResult(null)
  }
  // Solo PDF o Word: la IA saca las reglas para que se revisen aquí
  const upload = (file: File) => {
    if (!isDocument(file.name)) return toast(INVALID_DOCUMENT, { tone: 'err' })
    if (!canImport) return toast(NO_AI_FOR_DOCUMENTS, { tone: 'err' })
    importRules.mutate({ file, extra: { url, branch } })
  }
  const use = () =>
    check.mutate(text, {
      onSuccess: (validation) => {
        setResult(validation)
        if (!validation.valid) return
        onUse({ text, validation })
        onClose()
      },
    })

  return (
    <Modal onClose={onClose} className="max-w-3xl">
      <div className="p-5 sm:p-6">
        <div className="flex items-start justify-between gap-3 mb-1">
          <h2 className="font-semibold">{title}</h2>
          <button type="button" onClick={onClose} aria-label="Cerrar" className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
            <Icon name="x" className="w-5 h-5" />
          </button>
        </div>
        <p className="text-sm text-slate-500 mb-3">
          Se guardan en el proyecto (cargadas en la app) al iniciar el análisis y se usan en cada análisis mientras el repositorio no tenga un {RULES_FILENAME} válido.
          {canImport && ' También puedes subir el documento de requisitos (PDF o Word) y la IA saca las reglas.'}
        </p>
        <div className="mb-3">
          <DocumentDropzone onFile={upload} busy={importRules.isPending} />
        </div>
        {importRules.isPending && (
          <p className="mb-3 flex items-center gap-2 text-sm text-slate-500">
            <Spinner className="w-4 h-4" />
            Leyendo el documento con IA… puede tardar hasta 30 segundos.
          </p>
        )}
        {notice && <ImportNotice imported={notice} />}
        <textarea
          value={text}
          onChange={(e) => update(e.target.value)}
          spellCheck={false}
          aria-label="Reglas de negocio para este análisis"
          className="w-full min-h-80 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-950 text-slate-100 font-mono text-xs leading-relaxed p-4 outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15"
        />
        {result && <ValidationResult result={result} />}
        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => check.mutate(text, { onSuccess: setResult })} disabled={!text.trim() || check.isPending || importRules.isPending}>
            {check.isPending ? <Spinner className="w-4 h-4" /> : <Icon name="check" className="w-4 h-4" />}
            Validar
          </Button>
          <Button onClick={use} disabled={!text.trim() || check.isPending || importRules.isPending}>
            <Icon name="play" className="w-4 h-4" />
            Usar en este análisis
          </Button>
          <Button variant="secondary" onClick={() => saveText(RULES_FILENAME, text)} disabled={!text.trim()}>
            <Icon name="download" className="w-4 h-4" />
            Descargar para el repo
          </Button>
        </div>
      </div>
    </Modal>
  )
}

/**
 * Reglas de negocio en Nuevo análisis: al escribir la URL y la rama se revisa el reglas_negocio.toml del repo
 * (sin clonar) y se puede corregir o escribir aquí. Nunca bloquea el análisis.
 */
export function RulesPrecheck({ url, branch, rules, onRulesChange }: {
  url: string
  branch: string
  rules: FormRules | null
  onRulesChange: (rules: FormRules | null) => void
}) {
  const [debouncedUrl, debouncedBranch] = useDebounced(`${url.trim()}\n${branch.trim() || 'main'}`, DEBOUNCE_MS).split('\n')
  const target = { repo: githubRepo(debouncedUrl), url: debouncedUrl, branch: debouncedBranch }
  const [editing, setEditing] = useState<{ initial: string; title: string; imported?: ImportedRules } | null>(null)
  const { data, error, isFetching } = useQuery({
    queryKey: ['rules-precheck', target.repo, target.branch],
    queryFn: () => rulesApi.precheck(target.url, target.branch),
    enabled: Boolean(target.repo),
    retry: false,
    staleTime: 30_000,
  })

  if (!target.repo || !githubRepo(url)) return null

  const header = <p className="block text-sm font-medium mb-1.5 text-slate-700 dark:text-slate-300">Reglas de negocio</p>
  if (isFetching && !data)
    return (
      <div>
        {header}
        <p className="flex items-center gap-2 rounded-xl border border-slate-200 dark:border-slate-800 p-3.5 text-sm text-slate-500">
          <Spinner className="w-4 h-4" />
          Revisando {RULES_FILENAME} de {target.repo}…
        </p>
      </div>
    )
  if (error || !data)
    return error ? (
      <div>
        {header}
        <p className="rounded-xl border border-slate-200 dark:border-slate-800 p-3.5 text-sm text-slate-500">No se pudieron revisar las reglas ({error.message}). Se revisan al analizar.</p>
      </div>
    ) : null

  const view = precheckView(data, rules?.validation ?? null)
  const tone = TONE[view.tone]
  const warnings = rules ? rules.validation.warnings : view.uses === 'repo' ? data.file?.warnings : undefined
  const open = (initial: string, title: string) => setEditing({ initial, title })
  const appRules = data.uploaded?.valid ? data.uploaded.content : null

  return (
    <div>
      {/* Sacar las reglas del documento se hace después de analizar, en el asistente de Configuración → Reglas (paso a
          paso, con las preguntas una por una): aquí solo se avisa. El TOML y la importación en bruto abrumaban. */}
      {header}
      <section aria-label="Reglas de negocio" aria-busy={isFetching} className={cn('rounded-xl border p-3.5 text-sm', tone.box)}>
        <div className="flex gap-3">
          <Icon name={tone.icon} className={cn('w-5 h-5 shrink-0 mt-0.5', tone.iconClass)} />
          <div className="min-w-0 flex-1">
            <p className="font-medium">{view.title}</p>
            {view.detail && <p className={cn('mt-0.5 text-slate-600 dark:text-slate-300', view.tone === 'error' && 'font-mono text-xs')}>{view.detail}</p>}
            {warnings?.map((w) => (
              <p key={w} className="mt-1 font-mono text-xs text-amber-700 dark:text-amber-300">
                Aviso: {w}
              </p>
            ))}
            <div className="mt-2.5 flex flex-wrap gap-2">
              {rules ? (
                <>
                  <Button variant="secondary" onClick={() => open(rules.text, 'Editar reglas de este análisis')}>
                    <Icon name="code" className="w-4 h-4" />
                    Editar
                  </Button>
                  <Button variant="secondary" onClick={() => saveText(RULES_FILENAME, rules.text)}>
                    <Icon name="download" className="w-4 h-4" />
                    Descargar para el repo
                  </Button>
                  <Button variant="ghost" onClick={() => onRulesChange(null)}>
                    Quitar
                  </Button>
                </>
              ) : data.status === 'invalid' ? (
                <>
                  <Button variant="secondary" onClick={() => open(appRules ?? data.file?.content ?? data.template, `Corregir ${data.file?.path ?? RULES_FILENAME}`)}>
                    <Icon name="wand" className="w-4 h-4" />
                    Corregir
                  </Button>
                  {view.uses === null && (
                    <Button type="submit" variant="ghost">
                      Analizar sin reglas
                    </Button>
                  )}
                </>
              ) : null}
            </div>
          </div>
        </div>
      </section>
      {editing && (
        <RulesModal
          url={target.url}
          branch={target.branch}
          initial={editing.initial}
          title={editing.title}
          canImport={data.can_import}
          imported={editing.imported}
          onUse={onRulesChange}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  )
}
