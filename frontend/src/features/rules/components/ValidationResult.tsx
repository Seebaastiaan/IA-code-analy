import { SeverityBadge } from '@/shared/ui'
import type { RulesValidation } from '../types'

/** Resultado de validar un reglas_negocio.toml: el error con su línea o las reglas que se leyeron. */
export function ValidationResult({ result }: { result: RulesValidation }) {
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
