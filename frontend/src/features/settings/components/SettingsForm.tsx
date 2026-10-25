import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { invalidateAnalysis } from '@/shared/api/invalidate'
import { CAT } from '@/shared/constants/categories'
import { toast } from '@/shared/hooks/useToast'
import { CATEGORIES, type Category } from '@/shared/types/common'
import { Button, Card, ChipList, Icon, Input, Label, Spinner } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import { weightSum } from '@/shared/utils/score'
import { configApi, configQuery, useHealth } from '../api/config.api'
import type { ProjectConfig } from '../types'
import { toToml } from '../utils/toToml'

interface SettingsFormProps {
  repoId: string
  initial: ProjectConfig
}

function Services() {
  const { data } = useHealth()
  return (
    <Card className="p-5">
      <h2 className="font-semibold mb-4">Servicios</h2>
      <div className="space-y-3">
        {data?.services.map((s) => (
          <div key={s.id} className="flex items-center gap-3">
            <span className={cn('w-2 h-2 rounded-full', s.status === 'ok' ? 'bg-emerald-500' : s.status === 'down' ? 'bg-rose-500' : 'bg-slate-400')} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium">{s.name}</p>
              <p className="text-xs text-slate-400 truncate">{s.role}</p>
            </div>
            <span className={cn('text-xs', s.status === 'ok' ? 'text-emerald-600 dark:text-emerald-400' : s.status === 'down' ? 'text-rose-600 dark:text-rose-400' : 'text-slate-400')}>{s.label}</span>
          </div>
        )) ?? <p className="text-sm text-slate-400">Consultando…</p>}
      </div>
    </Card>
  )
}

export function SettingsForm({ repoId, initial }: SettingsFormProps) {
  const queryClient = useQueryClient()
  const [config, setConfig] = useState(initial)
  const sum = weightSum(config.weights)
  const dirty = JSON.stringify(config) !== JSON.stringify(initial)

  const setWeight = (k: Category, v: number) => setConfig((c) => ({ ...c, weights: { ...c.weights, [k]: v } }))
  const setThreshold = (k: 'score' | 'cov', v: number) => setConfig((c) => ({ ...c, thresholds: { ...c.thresholds, [k]: Math.max(0, Math.min(100, v)) } }))

  const save = useMutation({
    mutationFn: () => configApi.save(repoId, config),
    onSuccess: (saved) => {
      queryClient.setQueryData(configQuery(repoId).queryKey, saved)
      void invalidateAnalysis(queryClient)
      toast('Configuración guardada')
    },
    onError: (e) => toast(e.message, { tone: 'err' }),
  })

  return (
    <div className="grid lg:grid-cols-3 gap-4">
      <div className="lg:col-span-2 space-y-4">
        <Card className="p-5 sm:p-6">
          <div className="flex items-center justify-between mb-1">
            <h2 className="font-semibold">Pesos del score</h2>
            <span className={cn('text-xs font-semibold', sum === 100 ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400')}>Suma: {sum}%</span>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-5">Cuánto aporta cada categoría al score global.</p>
          <div className="space-y-5">
            {CATEGORIES.map((k) => (
              <div key={k}>
                <div className="flex items-center gap-2 mb-2">
                  <span className={cn('w-7 h-7 rounded-lg grid place-items-center', CAT[k].soft)}>
                    <Icon name={CAT[k].icon} className="w-4 h-4" />
                  </span>
                  <label htmlFor={`w-${k}`} className="text-sm font-medium">
                    {CAT[k].label}
                  </label>
                  <span className="ml-auto font-mono text-sm font-semibold">{config.weights[k]}%</span>
                </div>
                <input id={`w-${k}`} type="range" min={0} max={100} step={5} value={config.weights[k]} onChange={(e) => setWeight(k, Number(e.target.value))} className="w-full" />
              </div>
            ))}
          </div>
          {sum === 0 ? (
            <p className="mt-4 text-xs text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-500/10 rounded-lg p-3">Al menos una categoría debe tener peso mayor que 0.</p>
          ) : (
            sum !== 100 && (
              <p className="mt-4 text-xs text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-500/10 rounded-lg p-3">Los pesos no suman 100 %; se normalizarán automáticamente al calcular.</p>
            )
          )}
        </Card>

        <Card className="p-5 sm:p-6">
          <h2 className="font-semibold mb-4">Umbrales mínimos</h2>
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <Label htmlFor="thr-score">Score global mínimo</Label>
              <Input id="thr-score" type="number" min={0} max={100} value={config.thresholds.score} onChange={(e) => setThreshold('score', Number(e.target.value))} />
              <p className="text-xs text-slate-400 mt-1">Por debajo, el reporte se marca en rojo.</p>
            </div>
            <div>
              <Label htmlFor="thr-cov">Cobertura mínima (%)</Label>
              <Input id="thr-cov" type="number" min={0} max={100} value={config.thresholds.cov} onChange={(e) => setThreshold('cov', Number(e.target.value))} />
              <p className="text-xs text-slate-400 mt-1">Archivos por debajo generan un hallazgo.</p>
            </div>
          </div>
        </Card>

        <div className="grid sm:grid-cols-2 gap-4">
          <Card className="p-5">
            <h2 className="font-semibold mb-1">Reglas ignoradas</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-3">Códigos de Bandit o Ruff.</p>
            <ChipList items={config.ignored} onChange={(ignored) => setConfig((c) => ({ ...c, ignored }))} placeholder="p. ej. E501" />
          </Card>
          <Card className="p-5">
            <h2 className="font-semibold mb-1">Rutas excluidas</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-3">No se analizan.</p>
            <ChipList items={config.excluded} onChange={(excluded) => setConfig((c) => ({ ...c, excluded }))} placeholder="p. ej. scripts/" />
          </Card>
        </div>
      </div>

      <div className="space-y-4">
        <Services />
        <section className="rounded-2xl bg-slate-950 border border-slate-800 overflow-hidden">
          <div className="px-4 py-2.5 border-b border-slate-800 flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400">.ia_voy.toml</span>
            <span className="text-[10px] text-slate-500">vista previa en vivo</span>
          </div>
          <pre className="p-4 text-xs font-mono text-slate-300 overflow-x-auto scroll-thin leading-relaxed">{toToml(config)}</pre>
        </section>
        <Button className="w-full" onClick={() => save.mutate()} disabled={!dirty || sum === 0 || save.isPending}>
          {save.isPending ? <Spinner /> : <Icon name="save" className="w-4 h-4" />}
          Guardar configuración
        </Button>
        {dirty && (
          <Button variant="ghost" className="w-full" onClick={() => setConfig(initial)}>
            Descartar cambios
          </Button>
        )}
      </div>
    </div>
  )
}
