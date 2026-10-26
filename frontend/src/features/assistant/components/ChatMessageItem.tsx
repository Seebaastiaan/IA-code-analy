import { Link } from 'react-router'
import { useApplyFix } from '@/features/editor/hooks/useApplyFix'
import type { Finding } from '@/features/findings'
import { paths } from '@/shared/constants/paths'
import { Icon, MiniMarkdown } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import type { ChatMessage } from '../types'

const AiAvatar = () => (
  <span className="w-7 h-7 shrink-0 rounded-lg bg-brand-100 dark:bg-brand-500/15 text-brand-600 dark:text-brand-300 grid place-items-center">
    <Icon name="sparkle" className="w-3.5 h-3.5" />
  </span>
)

export function TypingIndicator() {
  return (
    <div className="flex gap-3" aria-label="El asistente está escribiendo">
      <AiAvatar />
      <div className="rounded-2xl bg-slate-100 dark:bg-slate-800 px-4 py-3 dot-typing text-lg leading-none text-slate-400">
        <span>●</span>
        <span>●</span>
        <span>●</span>
      </div>
    </div>
  )
}

interface ChatMessageItemProps {
  message: ChatMessage
  repoId: string
  /** Hallazgos del reporte, para resolver la acción "Aplicar fix" */
  findings: Finding[]
}

export function ChatMessageItem({ message: m, repoId, findings }: ChatMessageItemProps) {
  const applyFix = useApplyFix(repoId)

  if (m.role === 'me')
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-brand-600 text-white px-4 py-2.5 text-sm whitespace-pre-wrap">{m.content}</div>
      </div>
    )

  const target = m.action ? findings.find((f) => f.id === m.action!.finding_id && f.status === 'open') : undefined

  return (
    <div className="flex gap-3">
      <AiAvatar />
      <div className="max-w-[85%] min-w-0">
        <div
          className={cn(
            'rounded-2xl rounded-tl-md px-4 py-3 text-sm leading-relaxed [&_code]:font-mono [&_code]:text-[12px] [&_code]:bg-white dark:[&_code]:bg-slate-900 [&_code]:px-1 [&_code]:rounded',
            m.error ? 'bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300' : 'bg-slate-100 dark:bg-slate-800',
          )}
        >
          <MiniMarkdown text={m.content} />
        </div>
        {(m.sources?.length || target) && (
          <div className="flex flex-wrap items-center gap-1.5 mt-2">
            {m.sources?.map((s) => (
              <Link
                key={`${s.file}:${s.line}`}
                to={paths.editor(repoId, { file: s.file, line: s.line })}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 dark:border-slate-700 px-2 py-1 text-[11px] font-mono hover:border-brand-400 hover:text-brand-600 dark:hover:text-brand-300 transition"
              >
                <Icon name="file" className="w-3 h-3" />
                {s.file}:{s.line}
              </Link>
            ))}
            {target && m.action && (
              <button
                type="button"
                onClick={() => applyFix.mutate([target])}
                disabled={applyFix.isPending}
                className="inline-flex items-center gap-1 rounded-lg bg-brand-600 hover:bg-brand-700 text-white px-2 py-1 text-[11px] font-semibold disabled:opacity-50"
              >
                <Icon name="wand" className="w-3 h-3" />
                {m.action.label}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
