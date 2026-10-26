import { useState, type ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import type { Finding } from '@/features/findings'
import { CAT } from '@/shared/constants/categories'
import { paths } from '@/shared/constants/paths'
import { BRAND_HEX, TONE, tone } from '@/shared/constants/tones'
import type { Scores } from '@/shared/types/common'
import { Card, CategoryChip, DeltaBadge, EmptyState, ErrorState, Icon, Label, PageHeader, PageLoader, Select, SeverityBadge, Skeleton } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import { f1 } from '@/shared/utils/score'
import { useAnalyses, useDiff } from '../api/compare.api'

const METRICS: { key: keyof Scores; label: string; color: string }[] = [
  { key: 'global', label: 'Global', color: BRAND_HEX },
  { key: 'seg', label: CAT.seg.label, color: CAT.seg.hex },
  { key: 'test', label: CAT.test.label, color: CAT.test.hex },
  { key: 'prac', label: CAT.prac.label, color: CAT.prac.hex },
]

function DeltaCard({ label, color, a, b }: { label: string; color: string; a: number; b: number }) {
  return (
    <Card className="p-5">
      <p className="text-sm font-medium flex items-center gap-2">
        <span className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
        {label}
      </p>
      <div className="flex items-baseline gap-2 mt-2">
        <span className="text-slate-400 tabular-nums">{f1(a)}</span>
        <span className="text-slate-300">→</span>
        <span className={cn('text-2xl font-bold tabular-nums', TONE[tone(b)].text)}>{f1(b)}</span>
        <span className="ml-auto">
          <DeltaBadge delta={b - a} />
        </span>
      </div>
      <div className="mt-3 space-y-1.5">
        {[
          ['A', a, undefined],
          ['B', b, color],
        ].map(([l, v, c]) => (
          <div key={String(l)} className="flex items-center gap-2 text-[11px] text-slate-400">
            <span className="w-3">{l}</span>
            <div className="flex-1 h-1.5 rounded-full bg-slate-100 dark:bg-slate-800">
              <div className={cn('h-full rounded-full', !c && 'bg-slate-300 dark:bg-slate-600')} style={{ width: `${v}%`, background: c as string | undefined }} />
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}

function FindingList({ title, icon, tone: t, items, render }: { title: string; icon: 'plus' | 'check'; tone: 'new' | 'resolved'; items: Finding[]; render: (f: Finding) => ReactNode }) {
  return (
    <Card className="overflow-hidden">
      <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center gap-2">
        <span
          className={cn(
            'w-7 h-7 rounded-lg grid place-items-center',
            t === 'new' ? 'bg-rose-100 text-rose-600 dark:bg-rose-500/15 dark:text-rose-400' : 'bg-emerald-100 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400',
          )}
        >
          <Icon name={icon} className="w-4 h-4" />
        </span>
        <h2 className="font-semibold">{title}</h2>
        <span className="ml-auto text-sm text-slate-400">{items.length}</span>
      </div>
      <div className="divide-y divide-slate-100 dark:divide-slate-800">{items.length ? items.map(render) : <p className="px-5 py-4 text-sm text-slate-400">Ninguno</p>}</div>
    </Card>
  )
}

export default function ComparePage() {
  const { repoId = '' } = useParams()
  const analyses = useAnalyses(repoId)
  const [base, setBase] = useState<string | null>(null)
  const [target, setTarget] = useState<string | null>(null)
  // Por defecto: el penúltimo contra el último
  const a = base ?? analyses.data?.[1]?.id ?? null
  const b = target ?? analyses.data?.[0]?.id ?? null
  const diff = useDiff(a, b)

  if (analyses.error) return <ErrorState error={analyses.error} onRetry={() => void analyses.refetch()} />
  if (analyses.isPending) return <PageLoader />

  return (
    <>
      <PageHeader title="Comparativa" subtitle="Diferencias entre dos análisis del mismo repositorio." />
      {analyses.data.length < 2 ? (
        <Card>
          <EmptyState icon="compare" title="Se necesitan al menos dos análisis para comparar" />
        </Card>
      ) : (
        <>
          <Card className="p-5 grid sm:grid-cols-[1fr_auto_1fr] gap-3 items-end">
            <div>
              <Label htmlFor="cmp-a">Base (A)</Label>
              <Select id="cmp-a" value={a ?? ''} onChange={(e) => setBase(e.target.value)}>
                {analyses.data.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.label}
                  </option>
                ))}
              </Select>
            </div>
            <span className="hidden sm:grid w-10 h-10 rounded-full bg-slate-100 dark:bg-slate-800 place-items-center text-slate-400 mb-0.5">
              <Icon name="arrow" className="w-4 h-4" />
            </span>
            <div>
              <Label htmlFor="cmp-b">Comparar con (B)</Label>
              <Select id="cmp-b" value={b ?? ''} onChange={(e) => setTarget(e.target.value)}>
                {analyses.data.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.label}
                  </option>
                ))}
              </Select>
            </div>
          </Card>

          {diff.error ? (
            <ErrorState error={diff.error} onRetry={() => void diff.refetch()} />
          ) : !diff.data ? (
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-32" />
              ))}
            </div>
          ) : (
            <>
              <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
                {METRICS.map((m) => (
                  <DeltaCard key={m.key} label={m.label} color={m.color} a={diff.data.a[m.key]} b={diff.data.b[m.key]} />
                ))}
              </div>
              <div className="grid lg:grid-cols-2 gap-4 mt-4">
                <FindingList
                  title="Nuevos en B"
                  icon="plus"
                  tone="new"
                  items={diff.data.new}
                  render={(f) => (
                    <Link key={f.id} to={paths.report(repoId, b ?? 'latest', { finding: f.id })} className="w-full text-left px-5 py-3 flex items-center gap-3 hover:bg-slate-50 dark:hover:bg-slate-800/40">
                      <SeverityBadge sev={f.sev} />
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">{f.msg}</p>
                        <p className="text-xs font-mono text-slate-400">
                          {f.file}:{f.line}
                        </p>
                      </div>
                    </Link>
                  )}
                />
                <FindingList
                  title="Resueltos en B"
                  icon="check"
                  tone="resolved"
                  items={diff.data.resolved}
                  render={(f) => (
                    <div key={f.id} className="px-5 py-3 flex items-center gap-3">
                      <CategoryChip cat={f.cat} />
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate line-through decoration-emerald-500/60">{f.msg}</p>
                        <p className="text-xs font-mono text-slate-400">
                          {f.file}:{f.line} · {f.rule}
                        </p>
                      </div>
                    </div>
                  )}
                />
              </div>
            </>
          )}
        </>
      )}
    </>
  )
}
