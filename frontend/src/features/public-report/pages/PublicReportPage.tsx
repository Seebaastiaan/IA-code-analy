import { useMutation, useQuery } from '@tanstack/react-query'
import { useState, type FormEvent, type ReactNode } from 'react'
import { useParams } from 'react-router'
import { ApiError } from '@/shared/api/errors'
import { CAT } from '@/shared/constants/categories'
import { SEV } from '@/shared/constants/severities'
import { TONE, tone } from '@/shared/constants/tones'
import { CATEGORIES } from '@/shared/types/common'
import { Button, Card, CategoryChip, Chip, CodeSnippet, EmptyState, Icon, Input, PageLoader, ProgressBar, ScoreRing, SeverityBadge, Spinner, ThemeToggle } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import { formatDateTime } from '@/shared/utils/format'
import { publicApi } from '../api/public.api'

function Shell({ children }: { children: ReactNode }) {
  return (
    <>
      <header className="border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 h-16 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-fuchsia-500 text-white grid place-items-center font-extrabold text-xs">IA</div>
          <span className="font-bold">IA voy</span>
          <Chip className="ml-1">
            <Icon name="eye" className="w-3 h-3" />
            Solo lectura
          </Chip>
          <ThemeToggle className="ml-auto" />
        </div>
      </header>
      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-8 animate-fade-in">{children}</main>
    </>
  )
}

function PasswordGate({ shareId, onUnlock }: { shareId: string; onUnlock: (token: string) => void }) {
  const [password, setPassword] = useState('')
  const unlock = useMutation({
    mutationFn: () => publicApi.unlock(shareId, password),
    onSuccess: ({ token }) => onUnlock(token),
  })
  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    unlock.mutate()
  }
  return (
    <div className="min-h-[60vh] grid place-items-center">
      <form onSubmit={onSubmit} className="w-full max-w-sm">
        <Card className="p-6 sm:p-8 text-center">
          <span className="mx-auto w-12 h-12 rounded-2xl bg-brand-100 dark:bg-brand-500/15 text-brand-600 dark:text-brand-300 grid place-items-center">
            <Icon name="lock" />
          </span>
          <h1 className="text-lg font-semibold mt-4">Reporte protegido</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 mb-5">Escribe la contraseña que te compartieron.</p>
          <Input type="password" autoFocus value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Contraseña" aria-label="Contraseña" className="text-center" />
          {unlock.error && <p className="text-xs text-rose-600 dark:text-rose-400 mt-2">{unlock.error.message}</p>}
          <Button type="submit" className="w-full mt-3" disabled={!password || unlock.isPending}>
            {unlock.isPending && <Spinner />}
            Ver reporte
          </Button>
        </Card>
      </form>
    </div>
  )
}

const expiryText = (iso: string | null) => {
  if (!iso) return 'Este enlace no expira'
  const days = Math.max(1, Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000))
  return `Este enlace expira en ${days} día(s)`
}

export default function PublicReportPage() {
  const { shareId = '' } = useParams()
  const [token, setToken] = useState<string | null>(null)
  const { data, error, isPending } = useQuery({
    queryKey: ['public', shareId, token],
    queryFn: () => publicApi.get(shareId, token),
    retry: false,
  })

  if (isPending)
    return (
      <Shell>
        <PageLoader />
      </Shell>
    )

  if (error) {
    const status = error instanceof ApiError ? error.status : 0
    return (
      <Shell>
        {status === 401 ? (
          <PasswordGate shareId={shareId} onUnlock={setToken} />
        ) : (
          <EmptyState icon={status === 410 ? 'clock' : 'alert'} title={status === 410 ? 'Este enlace expiró' : status === 404 ? 'Este enlace no existe' : 'No se pudo abrir el reporte'}>
            <p>Pide a quien te lo compartió que genere uno nuevo.</p>
          </EmptyState>
        )}
      </Shell>
    )
  }

  return (
    <Shell>
      <div className="rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 px-4 py-2.5 text-xs sm:text-sm text-amber-800 dark:text-amber-200 flex items-center gap-2 mb-6">
        <Icon name="clock" className="w-4 h-4 shrink-0" />
        {expiryText(data.expires_at)} · compartido por {data.shared_by}
      </div>
      <Card className="p-6 flex flex-col sm:flex-row items-center gap-6 text-center sm:text-left">
        <ScoreRing value={data.scores.global} size={120} stroke={10} />
        <div className="flex-1">
          <p className="text-sm text-slate-500 dark:text-slate-400">Reporte de calidad</p>
          <h1 className="text-2xl font-bold tracking-tight">{data.repo_name}</h1>
          <p className="text-sm text-slate-500 mt-1">
            Rama {data.branch} · commit <span className="font-mono">{data.commit}</span> · {formatDateTime(data.created_at)}
          </p>
        </div>
      </Card>
      <div className="grid sm:grid-cols-3 gap-3 mt-4">
        {CATEGORIES.map((k) => (
          <Card key={k} className="p-4">
            <div className="flex items-center gap-2">
              <span className={cn('w-8 h-8 rounded-lg grid place-items-center', CAT[k].soft)}>
                <Icon name={CAT[k].icon} className="w-4 h-4" />
              </span>
              <span className="text-sm font-medium">{CAT[k].label}</span>
              <span className={cn('ml-auto text-xl font-bold', TONE[tone(data.scores[k])].text)}>{data.scores[k]}</span>
            </div>
            <div className="mt-3">
              <ProgressBar value={data.scores[k]} className={CAT[k].bar} />
            </div>
          </Card>
        ))}
      </div>
      <Card className="mt-4 overflow-hidden">
        <div className="p-5 border-b border-slate-200 dark:border-slate-800">
          <h2 className="font-semibold">Hallazgos principales</h2>
        </div>
        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {data.findings.map((f) => (
            <div key={f.id} className="px-5 py-3">
              <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
                <div className="flex items-center gap-2 sm:w-36 shrink-0">
                  <SeverityBadge sev={f.sev} />
                  <span className="font-mono text-xs text-slate-500">{f.rule}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">{f.msg}</p>
                  <p className="text-xs font-mono text-slate-400">
                    {f.file}:{f.line}
                  </p>
                </div>
                <CategoryChip cat={f.cat} />
              </div>
              {data.include_code && f.snippet && (
                <div className="mt-3">
                  <CodeSnippet lines={f.snippet} mark={f.line} markClass={SEV[f.sev].line} />
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>
      <p className="text-center text-xs text-slate-400 mt-8">
        Generado con IA voy · los fragmentos de código {data.include_code ? 'están incluidos' : 'no se incluyen en este enlace'}
      </p>
    </Shell>
  )
}
