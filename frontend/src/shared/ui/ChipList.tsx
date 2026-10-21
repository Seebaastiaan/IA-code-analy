import { useState, type FormEvent } from 'react'
import { Button } from './Button'
import { Input } from './Field'
import { Icon } from './Icon'

interface ChipListProps {
  items: string[]
  onChange: (items: string[]) => void
  placeholder: string
}

/** Lista editable de etiquetas monoespaciadas (reglas ignoradas, rutas excluidas). */
export function ChipList({ items, onChange, placeholder }: ChipListProps) {
  const [value, setValue] = useState('')

  const add = (e: FormEvent) => {
    e.preventDefault()
    const v = value.trim()
    if (v && !items.includes(v)) onChange([...items, v])
    setValue('')
  }

  return (
    <>
      <div className="flex flex-wrap gap-2 mb-3">
        {items.length ? (
          items.map((x) => (
            <span key={x} className="inline-flex items-center gap-1 rounded-lg bg-slate-100 dark:bg-slate-800 pl-2.5 pr-1 py-1 text-xs font-mono">
              {x}
              <button
                type="button"
                onClick={() => onChange(items.filter((i) => i !== x))}
                className="p-0.5 rounded hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-400"
                aria-label={`Quitar ${x}`}
              >
                <Icon name="x" className="w-3 h-3" />
              </button>
            </span>
          ))
        ) : (
          <span className="text-xs text-slate-400">Ninguna</span>
        )}
      </div>
      <form onSubmit={add} className="flex gap-2">
        <Input value={value} onChange={(e) => setValue(e.target.value)} placeholder={placeholder} className="py-2 font-mono text-xs" />
        <Button type="submit" variant="secondary" className="py-2 shrink-0">
          Agregar
        </Button>
      </form>
    </>
  )
}
