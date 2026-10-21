import { highlightPython } from '@/shared/utils/highlight'
import { cn } from '@/shared/utils/cn'

export interface SnippetLine {
  line: number
  text: string
}

/** Líneas de código numeradas con resaltado; `mark` sombrea una línea (la del hallazgo). */
export function CodeSnippet({ lines, mark, markClass }: { lines: SnippetLine[]; mark?: number; markClass?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 overflow-x-auto scroll-thin text-xs font-mono py-2">
      {lines.map(({ line, text }) => (
        <div key={line} className={cn('flex', line === mark && markClass)}>
          <span className="w-10 shrink-0 text-right pr-3 text-slate-400 select-none">{line}</span>
          <span className="whitespace-pre pr-4">
            {highlightPython(text).map((t, i) => (
              <span key={i} className={t.cls}>
                {t.text}
              </span>
            ))}
          </span>
        </div>
      ))}
    </div>
  )
}
