import type { TreeEntry } from '@/features/repos'
import { SEV } from '@/shared/constants/severities'
import { Card, Icon, Select } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'

interface FileTreeProps {
  entries: TreeEntry[]
  active: string
  modified: (path: string) => boolean
  onSelect: (path: string) => void
}

export function FileTree({ entries, active, modified, onSelect }: FileTreeProps) {
  return (
    <Card className="p-3 hidden lg:block h-fit">
      <p className="px-2 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Archivos</p>
      {entries.map((e, i) => {
        // Encabezado de carpeta al empezar un grupo nuevo (la lista viene ordenada por carpeta)
        const header = e.dir && e.dir !== entries[i - 1]?.dir
        const isActive = e.path === active
        return (
          <div key={e.path}>
            {header && (
              <p className="flex items-center gap-1.5 px-2 pt-2 pb-1 text-xs text-slate-400">
                <Icon name="folder" className="w-3.5 h-3.5" />
                {e.dir}/
              </p>
            )}
            <button
              type="button"
              onClick={() => onSelect(e.path)}
              className={cn(
                'w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm transition',
                e.dir && 'pl-5',
                isActive ? 'bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300 font-medium' : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300',
              )}
            >
              <Icon name="file" className="w-4 h-4 shrink-0" />
              <span className="truncate font-mono text-xs">{e.path.split('/').pop()}</span>
              {modified(e.path) && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" title="Modificado" />}
              {e.worst && <span className={cn('ml-auto text-[10px] font-bold rounded-full px-1.5 ring-1 ring-inset', SEV[e.worst].chip)}>{e.open_findings}</span>}
            </button>
          </div>
        )
      })}
    </Card>
  )
}

/** En pantallas chicas el árbol se reemplaza por un selector. */
export function FileSelect({ entries, active, onSelect }: Omit<FileTreeProps, 'modified'>) {
  return (
    <Select value={active} onChange={(e) => onSelect(e.target.value)} aria-label="Archivo" className="lg:hidden">
      {entries.map((e) => (
        <option key={e.path} value={e.path}>
          {e.path}
          {e.open_findings ? ` (${e.open_findings})` : ''}
        </option>
      ))}
    </Select>
  )
}
