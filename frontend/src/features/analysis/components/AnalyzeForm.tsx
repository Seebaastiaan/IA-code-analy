import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { GithubRepoPicker, useGithubBranches, type GithubRepo } from '@/features/github'
import { useSelectedRepo } from '@/features/repos/store/selectedRepo.store'
import { useConfig } from '@/features/settings'
import { CAT } from '@/shared/constants/categories'
import { paths } from '@/shared/constants/paths'
import { toast } from '@/shared/hooks/useToast'
import { CATEGORIES } from '@/shared/types/common'
import { Button, Card, Icon, Input, Label, Select, Spinner, buttonClass } from '@/shared/ui'
import { DEFAULT_WEIGHTS } from '@/shared/utils/score'
import { analysisApi } from '../api/analysis.api'
import { ANALYZERS, WHAT_HAPPENS } from '../constants/jobSteps'
import { useJobStore } from '../store/job.store'
import type { AnalyzerId } from '../types'

const ALL: AnalyzerId[] = Object.values(ANALYZERS).flatMap((list) => list.map((a) => a.id))

function Option({ checked, onChange, title, desc }: { checked: boolean; onChange: (v: boolean) => void; title: string; desc: string }) {
  return (
    <label className="flex gap-3 rounded-xl border border-slate-200 dark:border-slate-800 p-3.5 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/40">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="mt-0.5 w-4 h-4 accent-brand-600" />
      <span>
        <span className="block text-sm font-medium">{title}</span>
        <span className="text-xs text-slate-500">{desc}</span>
      </span>
    </label>
  )
}

export function AnalyzeForm() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const connect = useJobStore((s) => s.connect)
  const repoId = useSelectedRepo((s) => s.repoId)
  const { data: config } = useConfig(repoId ?? '')
  const weights = repoId && config ? config.weights : DEFAULT_WEIGHTS

  const [url, setUrl] = useState(params.get('url') ?? '')
  const [branch, setBranch] = useState(params.get('branch') ?? 'main')
  const [analyzers, setAnalyzers] = useState<AnalyzerId[]>(ALL)
  const [sandbox, setSandbox] = useState(true)
  // Repo elegido de la cuenta de GitHub ("owner/repo"); escribir la URL a mano lo descarta
  const [ghRepo, setGhRepo] = useState<string | null>(null)
  const branches = useGithubBranches(ghRepo)

  const pickRepo = (repo: GithubRepo) => {
    setGhRepo(repo.full_name)
    setUrl(repo.html_url)
    setBranch(repo.default_branch)
  }

  const start = useMutation({
    mutationFn: analysisApi.start,
    onSuccess: ({ job_id }) => {
      connect(job_id)
      navigate(paths.job(job_id))
    },
    onError: (e) => toast(e.message, { tone: 'err' }),
  })

  const toggle = (id: AnalyzerId, on: boolean) => setAnalyzers((list) => (on ? [...list, id] : list.filter((x) => x !== id)))

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    // Una categoría sin analizadores no tendría score (el backend responde 422)
    const missing = CATEGORIES.filter((k) => !ANALYZERS[k].some((a) => analyzers.includes(a.id))).map((k) => CAT[k].label)
    if (missing.length) return toast(`Elige al menos un analizador de: ${missing.join(', ')}`, { tone: 'err' })
    start.mutate({ url: url.trim(), branch: branch.trim() || 'main', analyzers, sandbox })
  }

  const sum = weights.seg + weights.test + weights.prac || 1

  return (
    <div className="grid lg:grid-cols-3 gap-4">
      <form onSubmit={onSubmit} className="lg:col-span-2">
        <Card className="p-5 sm:p-6 space-y-6">
          <GithubRepoPicker selected={ghRepo} onSelect={pickRepo} />

          <div className="grid sm:grid-cols-3 gap-4">
            <div className="sm:col-span-2">
              <Label htmlFor="f-url">URL del repositorio</Label>
              <Input
                id="f-url"
                required
                type="url"
                value={url}
                onChange={(e) => {
                  setUrl(e.target.value)
                  setGhRepo(null)
                }}
                placeholder="https://github.com/equipo/api-pagos"
                className="font-mono text-[13px]"
              />
            </div>
            <div>
              <Label htmlFor="f-br">Rama</Label>
              {branches.data?.length ? (
                <Select id="f-br" value={branch} onChange={(e) => setBranch(e.target.value)} className="font-mono text-[13px]">
                  {branches.data.map((b) => (
                    <option key={b.name} value={b.name}>
                      {b.name}
                    </option>
                  ))}
                </Select>
              ) : (
                <Input id="f-br" value={branch} onChange={(e) => setBranch(e.target.value)} disabled={branches.isFetching} className="font-mono text-[13px]" />
              )}
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
                    <label key={a.id} className="flex items-center gap-2 py-1 text-sm cursor-pointer">
                      <input type="checkbox" checked={analyzers.includes(a.id)} onChange={(e) => toggle(a.id, e.target.checked)} className="w-4 h-4 rounded accent-brand-600" />
                      {a.label}
                    </label>
                  ))}
                </div>
              ))}
            </div>
          </fieldset>

          <Option checked={sandbox} onChange={setSandbox} title="Ejecutar en sandbox" desc="Corre pip-audit, pytest y coverage aislados (sin sandbox se simulan)" />

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
          {repoId && (
            <Link to={paths.settings(repoId)} className="block mt-2 text-xs font-medium text-brand-600 dark:text-brand-300 hover:underline">
              Cambiar pesos →
            </Link>
          )}
        </div>
      </aside>
    </div>
  )
}
