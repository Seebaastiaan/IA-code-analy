import type { Finding } from '@/features/findings/types'
import { GRADE } from '@/shared/constants/grades'
import { Card, CategoryChip, Chip, EmptyState, Icon, Input, SegmentedControl, Select, SeverityBadge } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import type { CatFilter, SevFilter } from '../hooks/useReportFilters'
import type { Report } from '../types'

const SEV_OPTIONS: { value: SevFilter; label: string }[] = [
  { value: 'todas', label: 'Todas' },
  { value: 'alta', label: 'Alta' },
  { value: 'media', label: 'Media' },
  { value: 'baja', label: 'Baja' },
]

const CAT_OPTIONS: { value: CatFilter; label: string }[] = [
  { value: 'todas', label: 'Todas las categorías' },
  { value: 'seg', label: 'Seguridad' },
  { value: 'test', label: 'Pruebas' },
  { value: 'prac', label: 'Buenas prácticas' },
]

interface FindingsTabProps {
  findings: Finding[]
  q: string
  sev: SevFilter
  cat: CatFilter
  onChange: (patch: { q?: string; sev?: SevFilter; cat?: CatFilter }) => void
  onClear: () => void
}

export function FindingsTab({ findings, q, sev, cat, onChange, onClear }: FindingsTabProps) {
  const s = q.toLowerCase()
  const list = findings.filter(
    (f) => (sev === 'todas' || f.sev === sev) && (cat === 'todas' || f.cat === cat) && (!s || `${f.msg} ${f.file} ${f.rule} ${f.tool}`.toLowerCase().includes(s)),
  )

  return (
    <Card className="mt-4 overflow-hidden">
      <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex flex-col lg:flex-row gap-3 lg:items-center">
        <div className="relative flex-1">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
            <Icon name="search" className="w-4 h-4" />
          </span>
          <Input value={q} onChange={(e) => onChange({ q: e.target.value })} placeholder="Buscar por archivo, regla o texto…" aria-label="Buscar hallazgos" className="pl-9" />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SegmentedControl options={SEV_OPTIONS} value={sev} onChange={(v) => onChange({ sev: v })} />
          <Select value={cat} onChange={(e) => onChange({ cat: e.target.value as CatFilter })} aria-label="Categoría" className="w-auto py-2">
            {CAT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
        </div>
      </div>
      <div className="px-5 py-2 text-xs text-slate-400 bg-slate-50/60 dark:bg-slate-950/40 border-b border-slate-100 dark:border-slate-800">
        {list.length} resultados
      </div>
      <div className="divide-y divide-slate-100 dark:divide-slate-800">
        {!list.length ? (
          <EmptyState title="Sin hallazgos con esos filtros">
            <button type="button" onClick={onClear} className="text-brand-600 dark:text-brand-300 hover:underline">
              Limpiar filtros
            </button>
          </EmptyState>
        ) : (
          list.map((f) => {
            const done = f.status === 'resolved'
            return (
              <div key={f.id} className={cn('w-full text-left flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 px-4 sm:px-5 py-3.5', done && 'opacity-60')}>
                <div className="flex items-center gap-2 sm:w-44 shrink-0">
                  <SeverityBadge sev={f.sev} />
                  <span className="font-mono text-xs text-slate-500 truncate">{f.rule}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className={cn('text-sm font-medium', done && 'line-through')}>{f.msg}</p>
                  <p className="text-xs font-mono text-slate-400 truncate mt-0.5">
                    {f.file}:{f.line} · {f.tool}
                  </p>
                  <p className="text-xs text-slate-500 mt-1">{f.rec}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <CategoryChip cat={f.cat} />
                  {done ? (
                    <Chip tone="success">Resuelto</Chip>
                  ) : (
                    f.fix && (
                      <Chip tone="brand">
                        <Icon name="wand" className="w-3 h-3" />
                        Fix
                      </Chip>
                    )
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>
    </Card>
  )
}

export function CoverageTab({ coverage, threshold }: { coverage: Report['coverage']; threshold: number }) {
  return (
    <Card className="mt-4 p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold">Cobertura por archivo</h2>
        <span className="text-xs text-slate-400">Umbral mínimo: {threshold} %</span>
      </div>
      <div className="space-y-3">
        {coverage.map(({ file, percent: v }) => (
          <div key={file} className="grid grid-cols-[1fr_auto] sm:grid-cols-[14rem_1fr_3rem] items-center gap-x-3 gap-y-1">
            <span className="font-mono text-xs truncate">{file}</span>
            <span className={cn('sm:order-last text-right text-sm font-semibold tabular-nums', v < threshold && 'text-rose-600 dark:text-rose-400')}>{v}%</span>
            <div className="col-span-2 sm:col-span-1 relative h-2.5 rounded-full bg-slate-100 dark:bg-slate-800">
              <div className={cn('h-full rounded-full', v < threshold ? 'bg-rose-500' : v < 80 ? 'bg-amber-500' : 'bg-emerald-500')} style={{ width: `${v}%` }} />
              <div className="absolute -top-[3px] -bottom-[3px] w-0.5 bg-slate-400 dark:bg-slate-500" style={{ left: `${threshold}%` }} title="Umbral" />
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}

export function ComplexityTab({ complexity }: { complexity: Report['complexity'] }) {
  return (
    <Card className="mt-4 overflow-hidden">
      <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
        <h2 className="font-semibold">Complejidad ciclomática</h2>
        <div className="hidden sm:flex gap-1">
          {Object.entries(GRADE).map(([g, c]) => (
            <span key={g} className={cn('w-6 h-6 rounded-md text-white text-[11px] font-bold grid place-items-center', c)}>
              {g}
            </span>
          ))}
        </div>
      </div>
      <div className="divide-y divide-slate-100 dark:divide-slate-800">
        {complexity.map((c) => (
          <div key={`${c.file}:${c.fn}`} className="flex items-center gap-4 px-5 py-3">
            <span className={cn('w-8 h-8 rounded-lg text-white text-sm font-bold grid place-items-center shrink-0', GRADE[c.grade])}>{c.grade}</span>
            <div className="flex-1 min-w-0">
              <p className="font-mono text-sm truncate">{c.fn}()</p>
              <p className="text-xs text-slate-400 font-mono truncate">{c.file}</p>
            </div>
            <span className="text-sm tabular-nums">
              <b>{c.cc}</b> <span className="text-slate-400">CC</span>
            </span>
          </div>
        ))}
      </div>
    </Card>
  )
}
