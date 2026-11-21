import { Icon } from '@/shared/ui'
import type { ImportedRules } from '../types'
import { baseName } from '../utils/rules'

/** Las reglas del editor las propuso la IA desde un documento: de dónde salieron, qué se contradice y qué es ambiguo. */
export function ImportNotice({ imported }: { imported: ImportedRules }) {
  const contradictions = imported.contradictions ?? []
  return (
    <div role="status" className="mb-3 rounded-xl border border-brand-200 bg-brand-50/60 dark:border-brand-500/20 dark:bg-brand-500/5 px-3.5 py-2.5 text-sm">
      <p className="flex items-start gap-2 font-medium">
        <Icon name="wand" className="w-4 h-4 shrink-0 mt-0.5 text-brand-600 dark:text-brand-300" />
        <span>
          {imported.count} regla(s) sacadas de <code className="font-mono">{baseName(imported.source)}</code> por {imported.model}
        </span>
      </p>
      <p className="mt-0.5 text-slate-600 dark:text-slate-300">
        Revisa cada regla antes de usarlas: la IA puede equivocarse. Cada una dice de qué parte del documento salió (# Fuente).
      </p>
      {contradictions.length > 0 && (
        <>
          <p className="mt-2 font-medium text-rose-700 dark:text-rose-300">El documento se contradice</p>
          <ul className="mt-1 space-y-0.5 list-disc pl-5 text-rose-700 dark:text-rose-300">
            {contradictions.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
          <p className="mt-1 text-slate-600 dark:text-slate-300">
            Las dos versiones de cada una están en el editor, marcadas con <code className="font-mono"># CONTRADICCIÓN</code>. Deja solo la que vale y
            borra el comentario; mientras estén las dos, las reglas no se pueden usar.
          </p>
        </>
      )}
      {imported.doubts.length > 0 && (
        <>
          <p className="mt-2 font-medium text-amber-700 dark:text-amber-300">Dudas del documento</p>
          <ul className="mt-1 space-y-0.5 list-disc pl-5 text-amber-700 dark:text-amber-300">
            {imported.doubts.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
