import { useMutation } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { Link } from 'react-router'
import { invalidateAnalysis } from '@/shared/api/invalidate'
import { queryClient } from '@/shared/api/queryClient'
import { paths } from '@/shared/constants/paths'
import { toast } from '@/shared/hooks/useToast'
import { Button, Card, Icon, PageHeader, Spinner, buttonClass } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import { analysisApi } from '../api/analysis.api'
import { JOB_STEPS, NEXT_STEPS } from '../constants/jobSteps'
import { useJobStore } from '../store/job.store'
import type { Job } from '../types'

type StepState = 'ok' | 'run' | 'err' | 'wait'

function stepState(job: Job, i: number): StepState {
  if (i < job.step) return 'ok'
  if (i > job.step) return 'wait'
  if (job.status === 'error') return 'err'
  if (job.status === 'done') return 'ok'
  return job.status === 'running' ? 'run' : 'wait'
}

function StepIcon({ state }: { state: StepState }) {
  if (state === 'ok')
    return (
      <span className="w-6 h-6 rounded-full bg-emerald-500 text-white grid place-items-center">
        <Icon name="check" className="w-3.5 h-3.5" />
      </span>
    )
  if (state === 'run')
    return (
      <span className="w-6 h-6 rounded-full bg-brand-100 dark:bg-brand-500/15 text-brand-600 dark:text-brand-300 grid place-items-center">
        <Spinner className="w-3.5 h-3.5" />
      </span>
    )
  if (state === 'err')
    return (
      <span className="w-6 h-6 rounded-full bg-rose-500 text-white grid place-items-center">
        <Icon name="x" className="w-3.5 h-3.5" />
      </span>
    )
  return <span className="w-6 h-6 rounded-full border-2 border-slate-200 dark:border-slate-700" />
}

const logClass = (l: string) =>
  /ERROR/.test(l) ? 'text-rose-400' : /✓|completado/.test(l) ? 'text-emerald-400' : l.startsWith('$') ? 'text-brand-300' : l.startsWith('  ') ? 'text-slate-400' : ''

function Terminal({ job }: { job: Job }) {
  const ref = useRef<HTMLPreElement>(null)
  // Auto-scroll al final cuando llegan líneas nuevas
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [job.logs.length])

  return (
    <section className="lg:col-span-3 rounded-2xl bg-slate-950 border border-slate-800 overflow-hidden flex flex-col">
      <div className="px-4 py-2.5 border-b border-slate-800 flex items-center gap-2">
        <span className="w-2.5 h-2.5 rounded-full bg-rose-500/80" />
        <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
        <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
        <span className="ml-2 text-xs text-slate-400 font-mono truncate">ws://…/ws/jobs/{job.id}</span>
        {job.status === 'running' && (
          <span className="ml-auto flex items-center gap-1.5 text-[11px] text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            en vivo
          </span>
        )}
      </div>
      <pre ref={ref} className="flex-1 h-80 overflow-auto scroll-thin p-4 text-xs leading-relaxed font-mono text-slate-300">
        {job.logs.map((l, i) => (
          <span key={i} className={cn('block', logClass(l))}>
            {l}
          </span>
        ))}
      </pre>
    </section>
  )
}

export function JobView({ jobId }: { jobId: string }) {
  const { job, connect, markCancelled } = useJobStore()

  useEffect(() => {
    connect(jobId)
  }, [jobId, connect])

  const cancel = useMutation({
    mutationFn: () => analysisApi.cancel(jobId),
    onSuccess: () => {
      markCancelled()
      void invalidateAnalysis(queryClient)
      toast('Análisis cancelado', { tone: 'info' })
    },
  })
  const retry = useMutation({
    mutationFn: () => analysisApi.retry(jobId),
    onSuccess: () => connect(jobId, true),
    onError: (e) => toast(e.message, { tone: 'err' }),
  })

  if (!job || job.id !== jobId)
    return (
      <div className="grid place-items-center py-24 text-slate-400">
        <Spinner className="w-6 h-6" />
      </div>
    )

  const pct = Math.round((job.step / job.total) * 100)
  const err = job.status === 'error'
  const done = job.status === 'done'
  const cancelled = job.status === 'cancelled'

  return (
    <>
      <PageHeader
        eyebrow={
          <span className="flex items-center gap-1.5">
            <Icon name="branch" className="w-4 h-4" />
            {job.branch}
          </span>
        }
        title={<span className="break-all">{job.name}</span>}
        actions={
          <>
            {job.status === 'running' && (
              <Button variant="secondary" onClick={() => cancel.mutate()} disabled={cancel.isPending}>
                Cancelar
              </Button>
            )}
            {(err || cancelled) && (
              <>
                <Link to={paths.analyze({ url: job.url, branch: job.branch })} className={buttonClass('secondary')}>
                  Editar parámetros
                </Link>
                <Button onClick={() => retry.mutate()} disabled={retry.isPending}>
                  <Icon name="refresh" className="w-4 h-4" />
                  Reintentar
                </Button>
              </>
            )}
            {done && job.repo_id && (
              <>
                <Link to={paths.files(job.repo_id)} className={buttonClass('secondary')}>
                  Ver archivos
                </Link>
                <Link to={paths.repos()} className={buttonClass('primary')}>
                  Ver en Repositorios <Icon name="arrow" className="w-4 h-4" />
                </Link>
              </>
            )}
          </>
        }
      />

      <Card className="p-5 mb-4">
        <div className="flex items-center justify-between mb-2 text-sm">
          <span className="font-medium">
            {err ? 'El análisis se detuvo' : done ? 'Entorno listo · análisis guardado en el repositorio' : cancelled ? 'Análisis cancelado' : `${JOB_STEPS[job.step]?.name ?? ''}…`}
          </span>
          <span className={cn('font-mono tabular-nums', err ? 'text-rose-600 dark:text-rose-400' : 'text-slate-500')}>{pct}%</span>
        </div>
        <div className="h-2.5 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
          <div
            className={cn('h-full rounded-full transition-all duration-500', err ? 'bg-rose-500' : done ? 'bg-emerald-500' : cancelled ? 'bg-slate-400' : 'bg-gradient-to-r from-brand-500 to-fuchsia-500')}
            style={{ width: `${Math.max(pct, 3)}%` }}
          />
        </div>
        {err && job.error && (
          <div className="mt-4 rounded-xl bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-500/20 p-4 text-sm flex gap-3">
            <span className="text-rose-600 dark:text-rose-400">
              <Icon name="alert" />
            </span>
            <div>
              <p className="font-semibold text-rose-700 dark:text-rose-300">{job.error.title}</p>
              <p className="text-rose-700/80 dark:text-rose-300/80 mt-0.5">{job.error.hint ?? job.error.detail}</p>
            </div>
          </div>
        )}
      </Card>

      <div className="grid lg:grid-cols-5 gap-4">
        <Card className="p-5 lg:col-span-2">
          <h2 className="font-semibold mb-3">Pasos</h2>
          <ol className="space-y-1">
            {JOB_STEPS.map((s, i) => {
              const st = stepState(job, i)
              return (
                <li key={s.name} className={cn('flex items-center gap-3 rounded-lg px-2 py-1.5', st === 'run' && 'bg-brand-50/60 dark:bg-brand-500/5')}>
                  <StepIcon state={st} />
                  <span className={cn('text-sm', st === 'wait' ? 'text-slate-400' : st === 'err' ? 'text-rose-600 dark:text-rose-400 font-medium' : 'font-medium')}>{s.name}</span>
                </li>
              )
            })}
          </ol>
          <p className="mt-4 mb-1.5 px-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Siguientes sprints</p>
          <ol className="space-y-1">
            {NEXT_STEPS.map((s) => (
              <li key={s.name} className="flex items-center gap-3 rounded-lg px-2 py-1.5 opacity-60">
                <span className="w-6 h-6 rounded-full border-2 border-dashed border-slate-200 dark:border-slate-700" />
                <span className="text-sm text-slate-400 flex-1">{s.name}</span>
                <span className="text-[10px] font-mono text-slate-400">S{s.sprint}</span>
              </li>
            ))}
          </ol>
        </Card>
        <Terminal job={job} />
      </div>
    </>
  )
}
