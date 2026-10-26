import { useMemo } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { FindingDrawer, useFindingParam } from '@/features/findings'
import { useReport } from '@/features/report/api/report.api'
import { useRepoTree } from '@/features/repos'
import { SEV } from '@/shared/constants/severities'
import { Button, Card, Chip, EmptyState, ErrorState, Icon, PageHeader, PageLoader, SeverityBadge, Spinner, cardClass } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import { useFile } from '../api/file.api'
import { CodeDiff, CodeEditor } from '../components/CodeEditor'
import { FileSelect, FileTree } from '../components/FileTree'
import { useApplyFix } from '../hooks/useApplyFix'
import { useSaveFile } from '../hooks/useSaveFile'
import { fileKey, useEditorStore } from '../store/editor.store'

export default function EditorPage() {
  const { repoId = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const { findingId, open: openFinding, close: closeFinding } = useFindingParam()
  const tree = useRepoTree(repoId)
  const report = useReport(repoId)

  // Archivo activo: ?file= o el primero con hallazgos
  const path = params.get('file') ?? tree.data?.find((e) => e.open_findings)?.path ?? tree.data?.[0]?.path ?? null
  const line = Number(params.get('line')) || undefined
  const diff = params.get('diff') === '1'

  const file = useFile(repoId, path)
  const key = fileKey(repoId, path ?? '')
  const { drafts, pending, setDraft, discard } = useEditorStore()
  const draft = drafts[key]
  const pendingIds = useMemo(() => pending[key] ?? [], [pending, key])
  const content = draft ?? file.data?.content ?? ''
  const dirty = draft !== undefined && draft !== file.data?.content

  const applyFix = useApplyFix(repoId)
  const save = useSaveFile(repoId, path ?? '')

  // Memorizados: el editor solo repinta las marcas cuando cambian los hallazgos, no en cada tecla
  const findings = useMemo(() => report.data?.findings.filter((f) => f.file === path && f.status === 'open') ?? [], [report.data, path])
  const marked = useMemo(() => findings.filter((f) => !pendingIds.includes(f.id)), [findings, pendingIds])
  const fixable = marked.filter((f) => f.fix)
  const finding = report.data?.findings.find((f) => f.id === findingId)

  const setQuery = (patch: Record<string, string | null>) =>
    setParams((p) => {
      for (const [k, v] of Object.entries(patch)) if (v === null) p.delete(k)
      else p.set(k, v)
      return p
    })

  const selectFile = (p: string) => setQuery({ file: p, line: null, diff: null })
  const goToLine = (n: number) => setQuery({ line: String(n), diff: null })

  if (tree.error) return <ErrorState error={tree.error} onRetry={() => void tree.refetch()} />
  if (tree.isPending) return <PageLoader />
  if (!path) return <EmptyState icon="file" title="Este repositorio no tiene archivos analizados" />

  return (
    <>
      <PageHeader
        title="Editor"
        subtitle={`${report.data?.repo_name ?? ''} · los cambios se guardan en el repositorio clonado`}
        actions={<FileSelect entries={tree.data} active={path} onSelect={selectFile} />}
      />
      <div className="grid lg:grid-cols-[15rem_1fr] gap-4">
        <FileTree entries={tree.data} active={path} modified={(p) => drafts[fileKey(repoId, p)] !== undefined} onSelect={selectFile} />

        <section className="min-w-0">
          <div className={cn(cardClass, 'rounded-b-none border-b-0 px-3 sm:px-4 py-2.5 flex flex-wrap items-center gap-2')}>
            <span className="font-mono text-sm font-medium flex items-center gap-1.5">
              <Icon name="file" className="w-4 h-4 text-slate-400" />
              {path}
            </span>
            {dirty && <Chip tone="success">● modificado</Chip>}
            <div className="ml-auto flex flex-wrap gap-1.5">
              {fixable.length > 0 && (
                <Button variant="ghost" className="text-brand-600 dark:text-brand-300" onClick={() => applyFix.mutate(fixable)} disabled={applyFix.isPending}>
                  <Icon name="wand" className="w-4 h-4" />
                  Corregir todo ({fixable.length})
                </Button>
              )}
              <Button variant="ghost" aria-pressed={diff} className={cn(diff && 'bg-slate-100 dark:bg-slate-800')} onClick={() => setQuery({ diff: diff ? null : '1' })}>
                <Icon name="diff" className="w-4 h-4" />
                Diff
              </Button>
              {draft !== undefined && (
                <Button variant="ghost" onClick={() => discard(key)}>
                  Descartar
                </Button>
              )}
              <Button className="py-1.5 px-3" disabled={!dirty || save.isPending} onClick={() => save.mutate(content, { onSuccess: () => setQuery({ diff: null }) })}>
                {save.isPending ? <Spinner /> : <Icon name="save" className="w-4 h-4" />}
                {save.isPending ? 'Re-analizando…' : 'Guardar'}
              </Button>
            </div>
          </div>

          <div className="rounded-b-2xl border border-slate-200 dark:border-slate-800 overflow-hidden bg-white dark:bg-slate-900">
            {file.error ? (
              <ErrorState error={file.error} onRetry={() => void file.refetch()} />
            ) : !file.data ? (
              <PageLoader />
            ) : diff ? (
              <CodeDiff path={path} language={file.data.language} original={file.data.content} modified={content} />
            ) : (
              <CodeEditor path={path} language={file.data.language} value={content} onChange={(v) => setDraft(key, v)} findings={marked} revealLine={line} />
            )}
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-400 px-1">
            <span>{file.data?.language === 'python' ? 'Python 3.12' : file.data?.language}</span>
            <span>UTF-8</span>
            <span>Respaldo automático antes de guardar</span>
            {diff && <span className="sm:ml-auto">Izquierda: original · derecha: propuesta</span>}
          </div>

          {findings.length > 0 && (
            <Card className="mt-4 overflow-hidden">
              <div className="px-5 py-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                <h2 className="font-semibold text-sm">Hallazgos en este archivo</h2>
                <span className="text-xs text-slate-400">{findings.length}</span>
              </div>
              <div className="divide-y divide-slate-100 dark:divide-slate-800">
                {findings.map((f) => {
                  const isPending = pendingIds.includes(f.id)
                  return (
                    <div key={f.id} className={cn('flex flex-wrap items-center gap-x-3 gap-y-1 px-5 py-2.5', !isPending && SEV[f.sev].line)}>
                      <SeverityBadge sev={f.sev} />
                      <button type="button" onClick={() => goToLine(f.line)} className="font-mono text-xs text-slate-500 hover:text-brand-600 dark:hover:text-brand-300">
                        Línea {f.line}
                      </button>
                      <span className="text-sm flex-1 min-w-[12rem]">
                        <b className="font-mono text-xs">{f.rule}</b> · {f.msg}
                      </span>
                      {isPending ? (
                        <Chip tone="brand">Fix sin guardar</Chip>
                      ) : (
                        f.fix && (
                          <Button className="px-2 py-1 text-xs rounded-md" onClick={() => applyFix.mutate([f])} disabled={applyFix.isPending}>
                            <Icon name="wand" className="w-3 h-3" />
                            Aplicar fix
                          </Button>
                        )
                      )}
                      <button type="button" onClick={() => openFinding(f.id)} className="text-xs text-brand-600 dark:text-brand-300 hover:underline">
                        Detalle
                      </button>
                    </div>
                  )
                })}
              </div>
            </Card>
          )}
        </section>
      </div>

      {finding && <FindingDrawer finding={finding} repoId={repoId} pending={pendingIds.includes(finding.id)} onClose={closeFinding} />}
    </>
  )
}
