import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { GithubRepoPicker, useGithubBranches, type GithubRepo } from '@/features/github'
import { paths } from '@/shared/constants/paths'
import { toast } from '@/shared/hooks/useToast'
import { Button, Card, Icon, Input, Label, Select, Spinner, buttonClass } from '@/shared/ui'
import { analysisApi } from '../api/analysis.api'
import { NEXT_STEPS, WHAT_HAPPENS } from '../constants/jobSteps'
import { useJobStore } from '../store/job.store'

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

  const [url, setUrl] = useState(params.get('url') ?? '')
  const [branch, setBranch] = useState(params.get('branch') ?? 'main')
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

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    start.mutate({ url: url.trim(), branch: branch.trim() || 'main', sandbox })
  }

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

          <Option checked={sandbox} onChange={setSandbox} title="Ejecutar en el sandbox" desc="Entorno, dependencias y pip-audit dentro de WSL2 o Docker; sin sandbox el entorno se crea en el backend y pip-audit no corre" />

          <div className="flex flex-col-reverse sm:flex-row gap-2 sm:justify-end pt-2 border-t border-slate-100 dark:border-slate-800">
            <Link to={paths.repos()} className={buttonClass('secondary')}>
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
            Tiempo estimado: 1 – 3 minutos
          </p>
        </Card>
        <div className="rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 p-5 text-sm">
          <p className="font-medium mb-2">Próximos sprints</p>
          <ul className="space-y-1.5 text-xs text-slate-500">
            {NEXT_STEPS.map((s) => (
              <li key={s.name} className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-slate-300 dark:bg-slate-600" />
                <span className="flex-1">{s.name}</span>
                <span className="font-mono text-slate-400">S{s.sprint}</span>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  )
}
