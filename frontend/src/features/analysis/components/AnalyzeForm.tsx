import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { CAT } from '@/shared/constants/categories'
import { paths } from '@/shared/constants/paths'
import { toast } from '@/shared/hooks/useToast'
import { CATEGORIES } from '@/shared/types/common'
import { Button, Card, Icon, Input, Label, Spinner, buttonClass } from '@/shared/ui'
import { DEFAULT_WEIGHTS } from '@/shared/utils/score'
import { analysisApi } from '../api/analysis.api'
import { ANALYZERS, WHAT_HAPPENS } from '../constants/jobSteps'
import { useJobStore } from '../store/job.store'
import type { AnalyzerId } from '../types'

const ALL: AnalyzerId[] = Object.values(ANALYZERS).flatMap((list) => list.map((a) => a.id))
// pip-audit, pytest y coverage ejecutan el código del repo: hasta tener sandbox se simulan
const SIMULATED: AnalyzerId[] = ['pip-audit', 'pytest', 'coverage']

export function AnalyzeForm() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const connect = useJobStore((s) => s.connect)
  const weights = DEFAULT_WEIGHTS

  const [url, setUrl] = useState(params.get('url') ?? '')
  const [branch, setBranch] = useState(params.get('branch') ?? 'main')

  const start = useMutation({
    mutationFn: analysisApi.start,
    onSuccess: ({ job_id }) => {
      connect(job_id)
      navigate(paths.job(job_id))
    },
    onError: (e) => toast(e.message, { tone: 'err' }),
  })

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    start.mutate({ url: url.trim(), branch: branch.trim() || 'main', analyzers: ALL, sandbox: false, index: false })
  }

  const sum = weights.seg + weights.test + weights.prac || 1

  return (
    <div className="grid lg:grid-cols-3 gap-4">
      <form onSubmit={onSubmit} className="lg:col-span-2">
        <Card className="p-5 sm:p-6 space-y-6">
          <div className="grid sm:grid-cols-3 gap-4">
            <div className="sm:col-span-2">
              <Label htmlFor="f-url">URL del repositorio</Label>
              <Input
                id="f-url"
                required
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://github.com/equipo/api-pagos"
                className="font-mono text-[13px]"
              />
            </div>
            <div>
              <Label htmlFor="f-br">Rama</Label>
              <Input id="f-br" value={branch} onChange={(e) => setBranch(e.target.value)} className="font-mono text-[13px]" />
            </div>
          </div>

          <fieldset>
            <legend className="block text-sm font-medium mb-1.5 text-slate-700 dark:text-slate-300">Analizadores</legend>
            <div className="grid sm:grid-cols-3 gap-3">
              {CATEGORIES.map((k) => (
                <div key={k} className="rounded-xl border border-slate-200 dark:border-slate-800 p-3.5">
                  <div className="flex items-center gap-2 mb-2.5">
                    <span className={`w-7 h-7 rounded-lg grid place-items-center ${CAT[k].soft}`}>
                      <Icon name={CAT[k].icon} className="w-4 h-4" />
                    </span>
                    <span className="text-sm font-semibold">{CAT[k].label}</span>
                    <span className="ml-auto text-xs font-mono text-slate-400">{Math.round((weights[k] / sum) * 100)}%</span>
                  </div>
                  {ANALYZERS[k].map((a) => (
                    <p key={a.id} className="flex items-center gap-2 py-1 text-sm">
                      <Icon name="check" className="w-4 h-4 text-emerald-500" />
                      {a.label}
                      {SIMULATED.includes(a.id) && <span className="ml-auto text-[11px] text-slate-400">simulado</span>}
                    </p>
                  ))}
                </div>
              ))}
            </div>
          </fieldset>

          <div className="flex flex-col-reverse sm:flex-row gap-2 sm:justify-end pt-2 border-t border-slate-100 dark:border-slate-800">
            <Link to={paths.dashboard()} className={buttonClass('secondary')}>
              Cancelar
            </Link>
            <Button type="submit" disabled={start.isPending}>
              {start.isPending ? <Spinner /> : <Icon name="play" className="w-4 h-4" />}
              Iniciar análisis
            </Button>
          </div>
        </Card>
      </form>

      <aside className="space-y-4">
        <Card className="p-5">
          <h2 className="font-semibold mb-3">Qué va a pasar</h2>
          <ol className="space-y-3 text-sm">
            {WHAT_HAPPENS.map(([a, b], i) => (
              <li key={a} className="flex gap-3">
                <span className="w-6 h-6 shrink-0 rounded-full bg-slate-100 dark:bg-slate-800 text-xs font-bold grid place-items-center text-slate-500">{i + 1}</span>
                <div>
                  <p className="font-medium">{a}</p>
                  <p className="text-xs text-slate-500">{b}</p>
                </div>
              </li>
            ))}
          </ol>
          <p className="mt-4 flex items-center gap-2 text-xs text-slate-500">
            <Icon name="clock" className="w-4 h-4" />
            Tiempo estimado: 2 – 4 minutos
          </p>
        </Card>
        <div className="rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 p-5 text-sm">
          <p className="font-medium mb-1">Fórmula actual</p>
          <code className="font-mono text-xs text-slate-500">
            Score = {(weights.seg / sum).toFixed(2)}·Seg + {(weights.test / sum).toFixed(2)}·Test + {(weights.prac / sum).toFixed(2)}·Prác
          </code>
        </div>
      </aside>
    </div>
  )
}
