import { useMemo, useState } from 'react'
import { Icon } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import type { TreeEntry } from '../types'

interface Folder {
  name: string
  path: string
  folders: Folder[]
  files: TreeEntry[]
}

/** Arma carpetas anidadas a partir de las rutas planas del backend ("app/core/x.py"). */
function buildTree(entries: TreeEntry[]): Folder {
  const root: Folder = { name: '', path: '', folders: [], files: [] }
  for (const e of entries) {
    let node = root
    for (const part of e.dir ? e.dir.split('/') : []) {
      const path = node.path ? `${node.path}/${part}` : part
      let next = node.folders.find((f) => f.name === part)
      if (!next) {
        next = { name: part, path, folders: [], files: [] }
        node.folders.push(next)
      }
      node = next
    }
    node.files.push(e)
  }
  const sort = (f: Folder) => {
    f.folders.sort((a, b) => a.name.localeCompare(b.name))
    f.folders.forEach(sort)
  }
  sort(root)
  return root
}

/** Carpetas que contienen la ruta (para abrirlas al llegar con ?file=). */
const ancestors = (path: string) => path.split('/').slice(0, -1).map((_, i, parts) => parts.slice(0, i + 1).join('/'))

interface FolderTreeProps {
  entries: TreeEntry[]
  active: string | null
  onSelect: (path: string) => void
}

export function FolderTree({ entries, active, onSelect }: FolderTreeProps) {
  const root = useMemo(() => buildTree(entries), [entries])
  // Abiertas al inicio: las de primer nivel y las que llevan al archivo activo
  const [open, setOpen] = useState(() => new Set([...root.folders.map((f) => f.path), ...(active ? ancestors(active) : [])]))
  const toggle = (path: string) =>
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })

  const renderFolder = (folder: Folder, depth: number) => (
    <ul role={depth ? 'group' : 'tree'} aria-label={depth ? undefined : 'Archivos del repositorio'}>
      {folder.folders.map((f) => {
        const isOpen = open.has(f.path)
        return (
          <li key={f.path} role="treeitem" aria-expanded={isOpen}>
            <button
              type="button"
              onClick={() => toggle(f.path)}
              style={{ paddingLeft: `${depth * 14 + 8}px` }}
              className="w-full flex items-center gap-1.5 pr-2 py-1.5 rounded-lg text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <Icon name="chevron" className={cn('w-3.5 h-3.5 shrink-0 text-slate-400 transition-transform', isOpen && 'rotate-90')} />
              <Icon name="folder" className="w-4 h-4 shrink-0 text-amber-500" />
              <span className="truncate font-mono text-xs">{f.name}</span>
            </button>
            {isOpen && renderFolder(f, depth + 1)}
          </li>
        )
      })}
      {folder.files.map((e) => {
        const isActive = e.path === active
        return (
          <li key={e.path} role="treeitem" aria-selected={isActive}>
            <button
              type="button"
              onClick={() => onSelect(e.path)}
              style={{ paddingLeft: `${depth * 14 + 28}px` }}
              className={cn(
                'w-full flex items-center gap-1.5 pr-2 py-1.5 rounded-lg text-sm transition',
                isActive ? 'bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300 font-medium' : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300',
              )}
            >
              <Icon name="file" className="w-4 h-4 shrink-0 text-sky-500" />
              <span className="truncate font-mono text-xs">{e.path.split('/').pop()}</span>
            </button>
          </li>
        )
      })}
    </ul>
  )

  return renderFolder(root, 0)
}
