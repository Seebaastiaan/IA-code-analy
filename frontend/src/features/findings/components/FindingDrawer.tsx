import { Link } from 'react-router'
import { useApplyFix } from '@/features/editor/hooks/useApplyFix'
import { SEV } from '@/shared/constants/severities'
import { paths } from '@/shared/constants/paths'
import { Button, CategoryChip, Chip, CodeSnippet, Drawer, Icon, SeverityBadge, Spinner, buttonClass } from '@/shared/ui'
import { useIgnoreRule } from '../hooks/useIgnoreRule'
import type { Finding } from '../types'

interface FindingDrawerProps {
  finding: Finding
  repoId: string
  onClose: () => void
  /** Hallazgos con fix aplicado en el borrador, pendientes de guardar */
  pending?: boolean
}

export function FindingDrawer({ finding: f, repoId, onClose, pending }: FindingDrawerProps) {
  const applyFix = useApplyFix(repoId)
  const ignore = useIgnoreRule(repoId)
  const done = f.status === 'resolved'
  const question = `Explícame el hallazgo ${f.rule} en ${f.file}:${f.line}`

  return (
    <Drawer onClose={onClose}>
      <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <SeverityBadge sev={f.sev} />
            <CategoryChip cat={f.cat} />
            {done && (
              <Chip tone="success">
                <Icon name="check" className="w-3 h-3" />
                Resuelto
              </Chip>
            )}
            {pending && !done && <Chip tone="brand">Fix sin guardar</Chip>}
          </div>
          <h3 className="text-lg font-semibold leading-snug">{f.msg}</h3>
          <p className="mt-1 font-mono text-xs text-slate-500">
            {f.file}:{f.line} · {f.tool} · {f.rule}
          </p>
        </div>
        <button type="button" onClick={onClose} aria-label="Cerrar" className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400">
          <Icon name="x" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto scroll-thin p-5 space-y-5">
        {f.snippet && f.snippet.length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Código</p>
            <CodeSnippet lines={f.snippet} mark={f.line} markClass={SEV[f.sev].line} />
          </div>
        )}
        {f.why && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">Por qué importa</p>
            <p className="text-sm leading-relaxed">{f.why}</p>
          </div>
        )}
        {f.rec && (
          <div className="rounded-xl bg-brand-50 dark:bg-brand-500/10 border border-brand-100 dark:border-brand-500/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-brand-600 dark:text-brand-300 mb-1.5">Cómo corregirlo</p>
            <p className="text-sm leading-relaxed">{f.rec}</p>
          </div>
        )}
      </div>

      <div className="p-4 border-t border-slate-200 dark:border-slate-800 grid grid-cols-2 gap-2">
        {f.fix && !done && !pending && (
          <Button className="col-span-2" onClick={() => applyFix.mutate([f])} disabled={applyFix.isPending}>
            {applyFix.isPending ? <Spinner /> : <Icon name="wand" className="w-4 h-4" />}
            Aplicar corrección automática
          </Button>
        )}
        <Link to={paths.editor(repoId, { file: f.file, line: f.line })} onClick={onClose} className={buttonClass('secondary')}>
          <Icon name="code" className="w-4 h-4" />
          Abrir en editor
        </Link>
        <Link to={paths.assistant(repoId, question)} onClick={onClose} className={buttonClass('secondary')}>
          <Icon name="chat" className="w-4 h-4" />
          Preguntar a la IA
        </Link>
        <Button
          variant="ghost"
          className="col-span-2 text-slate-500"
          disabled={ignore.isPending}
          onClick={() => ignore.mutate(f.rule, { onSuccess: onClose })}
        >
          <Icon name="ban" className="w-4 h-4" />
          Ignorar la regla {f.rule} en este proyecto
        </Button>
      </div>
    </Drawer>
  )
}
