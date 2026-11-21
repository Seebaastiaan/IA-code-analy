import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Button, ErrorState, Icon, Spinner } from '@/shared/ui'
import { rulesApi } from '../api/rules.api'
import type { MatrixCell, PermissionMatrix, RuleTestsView } from '../types'
import { markedCells, matrixFromCode, matrixPayload, nextCell } from '../utils/rules'

const CELL_STYLE: Record<MatrixCell, string> = {
  permitido: 'bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-200 dark:border-emerald-500/30',
  prohibido: 'bg-rose-50 text-rose-800 border-rose-200 dark:bg-rose-500/10 dark:text-rose-200 dark:border-rose-500/30',
}

function Table({ matrix, onChange }: { matrix: PermissionMatrix; onChange: (m: PermissionMatrix) => void }) {
  const toggle = (actionId: string, role: string) =>
    onChange({
      ...matrix,
      actions: matrix.actions.map((a) => (a.id === actionId ? { ...a, cells: { ...a.cells, [role]: nextCell(a.cells[role]) } } : a)),
    })
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
      <table className="w-full text-xs">
        <thead className="bg-slate-50 dark:bg-slate-900/60 text-slate-500">
          <tr>
            <th scope="col" className="text-left font-medium px-3 py-2">Acción</th>
            {matrix.roles.map((r) => (
              <th key={r} scope="col" className="font-medium px-2 py-2 text-center">{r}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.actions.map((a) => (
            <tr key={a.id} className="border-t border-slate-100 dark:border-slate-800">
              <th scope="row" className="text-left font-normal px-3 py-1.5">
                <code className="font-mono">{a.id}</code>
                {a.suggested.length > 0 && <span className="block text-[11px] text-slate-400">El código hoy deja pasar: {a.suggested.join(', ')}</span>}
              </th>
              {matrix.roles.map((r) => {
                const cell = a.cells[r]
                return (
                  <td key={r} className="px-2 py-1.5 text-center">
                    <button
                      type="button"
                      onClick={() => toggle(a.id, r)}
                      aria-label={`${a.id} como ${r}: ${cell ?? 'fuera de la matriz'}`}
                      className={`min-w-20 rounded-lg border px-2 py-1 ${cell ? CELL_STYLE[cell] : 'border-dashed border-slate-300 text-slate-400 dark:border-slate-700'}`}
                    >
                      {cell ?? '—'}
                    </button>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/**
 * Matriz rol × acción de una regla de permisos (PROPUESTA_REGLAS_VERIFICABLES.md §6.3). El equipo marca cada celda; la
 * prueba sale de la tabla sin IA. Lo que hace el código se muestra como sugerencia: el oráculo es la regla.
 */
export function PermissionMatrixEditor({ repoId, ruleId, onSave, busy }: {
  repoId: string
  ruleId: string
  onSave: (fn: () => Promise<RuleTestsView>, done?: string) => void
  busy: boolean
}) {
  const { data, error, refetch } = useQuery({ queryKey: ['rules', repoId, 'matriz', ruleId], queryFn: () => rulesApi.matrix(repoId, ruleId), staleTime: 0 })
  const [draft, setDraft] = useState<PermissionMatrix | null>(null)

  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />
  if (!data) return <Spinner className="w-4 h-4" />
  const matrix = draft ?? data
  const marked = markedCells(matrix)
  return (
    <div className="space-y-2 rounded-xl border border-slate-200 dark:border-slate-800 p-3">
      <p className="text-xs text-slate-500">
        Marca qué puede hacer cada rol según la regla (clic: permitido → prohibido → fuera). Lo que no marques queda fuera de la prueba.
        La prueba sale de esta tabla, sin IA.
      </p>
      {matrix.actions.length ? (
        <Table matrix={matrix} onChange={setDraft} />
      ) : (
        <p className="text-sm text-slate-500">El mapa no encontró acciones con permisos (endpoints con usuario que escriben o que solo algunos roles usan).</p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          onClick={() => onSave(() => rulesApi.saveMatrix(repoId, ruleId, matrixPayload(matrix)), 'Prueba escrita desde la matriz: córrela y apruébala')}
          disabled={busy || marked === 0}
        >
          <Icon name="save" className="w-4 h-4" />
          Guardar y escribir la prueba ({marked})
        </Button>
        <Button variant="ghost" onClick={() => setDraft(matrixFromCode(matrix))} disabled={busy} title="Revisa cada celda: si el código tiene un error de permisos, copiarlo lo daría por bueno">
          Usar lo que hace el código
        </Button>
      </div>
    </div>
  )
}
