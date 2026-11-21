import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from '@/shared/hooks/useToast'
import { Button, Card, Chip, ErrorState, Icon, Spinner } from '@/shared/ui'
import { harnessQuery, rulesApi, useHarness } from '../api/rules.api'
import type { Harness, HarnessView, MapSummary } from '../types'
import { FRAMEWORK, HARNESS_ORIGIN, harnessStatus, mapSummary, smokeLabel } from '../utils/rules'

function MapLine({ map }: { map: MapSummary }) {
  if (!map.framework)
    return <p className="text-sm text-slate-500">{map.warnings[0] ?? 'No se reconoció FastAPI, Flask ni Django en el repositorio.'}</p>
  return (
    <div className="text-sm">
      <p className="flex flex-wrap items-center gap-2">
        <Chip tone="brand">{FRAMEWORK[map.framework] ?? map.framework}</Chip>
        <span>IA voy encontró {mapSummary(map)} en el código.</span>
      </p>
      {map.roles.length > 0 && (
        <p className="mt-1.5 text-slate-500">
          Roles: <span className="font-mono">{map.roles.join(', ')}</span>
        </p>
      )}
      {(map.integrations.length > 0 || map.uses_time) && (
        <p className="mt-1 text-slate-500">
          El arnés sustituye {[...map.integrations, ...(map.uses_time ? ['la hora'] : [])].join(', ')}: las pruebas nunca envían nada ni dependen del reloj.
        </p>
      )}
      {map.warnings.map((w) => (
        <p key={w} className="mt-1 text-amber-700 dark:text-amber-300">
          {w}
        </p>
      ))}
    </div>
  )
}

function Messages({ items, tone }: { items: string[]; tone: 'error' | 'warn' }) {
  if (!items.length) return null
  const color = tone === 'error' ? 'text-rose-700 dark:text-rose-300' : 'text-amber-700 dark:text-amber-300'
  return (
    <ul className={`mt-2 space-y-0.5 list-disc pl-5 text-sm ${color}`}>
      {items.map((m) => (
        <li key={m}>{m}</li>
      ))}
    </ul>
  )
}

function Smoke({ harness }: { harness: Harness }) {
  const [open, setOpen] = useState(false)
  if (harness.smoke === 'pendiente') return null
  if (harness.smoke === 'corriendo')
    return (
      <p role="status" className="mt-3 flex items-center gap-2 text-sm text-slate-500">
        <Spinner className="w-4 h-4" />
        Corriendo la prueba de humo en el sandbox: instala las dependencias del proyecto, así que puede tardar unos minutos.
      </p>
    )
  const ok = harness.smoke === 'paso'
  return (
    <div role="status" className={`mt-3 rounded-xl border px-3.5 py-2.5 text-sm ${ok ? 'border-emerald-200 bg-emerald-50/60 dark:border-emerald-500/20 dark:bg-emerald-500/5' : 'border-rose-200 bg-rose-50/60 dark:border-rose-500/20 dark:bg-rose-500/5'}`}>
      <p className={`font-medium ${ok ? 'text-emerald-700 dark:text-emerald-300' : 'text-rose-700 dark:text-rose-300'}`}>
        {ok ? 'La prueba de humo pasó' : 'La prueba de humo falló'}
      </p>
      {harness.smoke_message && <p className="mt-0.5 font-mono text-xs break-words">{harness.smoke_message}</p>}
      {harness.smoke_tests.length > 0 && (
        <>
          <button type="button" className="mt-1.5 text-xs text-brand-600 dark:text-brand-300 hover:underline" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
            {open ? 'Ocultar comprobaciones' : `Ver las ${harness.smoke_tests.length} comprobaciones`}
          </button>
          {open && (
            <ul className="mt-1.5 space-y-1">
              {harness.smoke_tests.map((t) => (
                <li key={t.name} className="flex flex-wrap items-baseline gap-2 text-xs">
                  <Chip tone={t.outcome === 'passed' ? 'success' : t.outcome === 'skipped' ? 'neutral' : 'danger'}>
                    {t.outcome === 'passed' ? 'Pasa' : t.outcome === 'skipped' ? 'Omitida' : 'Falla'}
                  </Chip>
                  <code className="font-mono">{smokeLabel(t.name)}</code>
                  {t.message && <span className="text-slate-500 break-words">{t.message}</span>}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}

function Editor({ repoId, view, harness }: { repoId: string; view: HarnessView; harness: Harness }) {
  const queryClient = useQueryClient()
  const [text, setText] = useState(harness.code)
  const [showCode, setShowCode] = useState(false)
  const set = (next: HarnessView) => queryClient.setQueryData(harnessQuery(repoId).queryKey, next)
  const fail = (e: Error) => toast(e.message, { tone: 'err' })

  const save = useMutation({
    mutationFn: () => rulesApi.editHarness(repoId, text),
    onSuccess: (v) => {
      set(v)
      toast('Arnés guardado: vuelve a correr la prueba de humo')
    },
    onError: fail,
  })
  const smoke = useMutation({ mutationFn: () => rulesApi.runSmoke(repoId), onSuccess: set, onError: fail })
  const approve = useMutation({
    mutationFn: () => rulesApi.approveHarness(repoId),
    onSuccess: (v) => {
      set(v)
      toast('Arnés aprobado: ya se pueden generar las pruebas de las reglas')
      void queryClient.invalidateQueries({ queryKey: ['rules', repoId, 'pruebas'] })
    },
    onError: fail,
  })
  const remove = useMutation({ mutationFn: () => rulesApi.removeHarness(repoId), onSuccess: set, onError: fail })

  const status = harnessStatus(harness)
  const running = harness.smoke === 'corriendo'
  const edited = text !== harness.code
  const busy = save.isPending || smoke.isPending || approve.isPending || remove.isPending || running
  const cantRun = harness.errors.length > 0 ? 'Corrige los errores del arnés' : !view.sandbox ? 'Configura SANDBOX=wsl o SANDBOX=docker' : edited ? 'Guarda los cambios primero' : undefined

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <Chip tone={status.tone}>{status.label}</Chip>
        <span className="text-sm text-slate-500">
          {HARNESS_ORIGIN[harness.origin]}
          {harness.origin === 'ia' && harness.model ? ` · ${harness.model}` : ''}
          {harness.source_path ? ` · ${harness.source_path}` : ''}
        </span>
        {harness.approved && harness.approved_by && <span className="text-xs text-slate-400">por {harness.approved_by}</span>}
      </div>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
        Fixtures: <span className="font-mono text-xs">{harness.fixtures.join(', ') || '—'}</span>
      </p>
      {harness.assumptions.length > 0 && (
        <div className="mt-2 text-sm">
          <p className="font-medium">Lo que la IA supuso</p>
          <ul className="mt-0.5 space-y-0.5 list-disc pl-5 text-slate-600 dark:text-slate-300">
            {harness.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </div>
      )}
      <Messages items={harness.errors} tone="error" />
      <Messages items={harness.warnings} tone="warn" />
      <Smoke harness={harness} />

      <button type="button" className="mt-3 text-sm text-brand-600 dark:text-brand-300 hover:underline" onClick={() => setShowCode((v) => !v)} aria-expanded={showCode}>
        {showCode ? 'Ocultar el código' : 'Ver y editar el código (conftest.py)'}
      </button>
      {showCode && (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          spellCheck={false}
          aria-label="Código del arnés (conftest.py)"
          className="mt-2 w-full min-h-96 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-950 text-slate-100 font-mono text-xs leading-relaxed p-4 outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15"
        />
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {edited && (
          <Button onClick={() => save.mutate()} disabled={busy || !text.trim()}>
            {save.isPending ? <Spinner className="w-4 h-4" /> : <Icon name="save" className="w-4 h-4" />}
            Guardar cambios
          </Button>
        )}
        <Button variant="secondary" onClick={() => smoke.mutate()} disabled={busy || Boolean(cantRun)} title={cantRun}>
          {running || smoke.isPending ? <Spinner className="w-4 h-4" /> : <Icon name="play" className="w-4 h-4" />}
          {harness.smoke === 'pendiente' ? 'Correr prueba de humo' : 'Volver a probar'}
        </Button>
        {!harness.approved && (
          <Button onClick={() => approve.mutate()} disabled={busy || harness.smoke !== 'paso' || edited} title={harness.smoke !== 'paso' ? 'Primero tiene que pasar la prueba de humo' : undefined}>
            {approve.isPending ? <Spinner className="w-4 h-4" /> : <Icon name="check" className="w-4 h-4" />}
            Aprobar arnés
          </Button>
        )}
        <Button variant="ghost" className="text-rose-600 dark:text-rose-400" onClick={() => remove.mutate()} disabled={busy}>
          Quitar
        </Button>
      </div>
    </>
  )
}

function Start({ repoId, view }: { repoId: string; view: HarnessView }) {
  const queryClient = useQueryClient()
  const set = (next: HarnessView) => queryClient.setQueryData(harnessQuery(repoId).queryKey, next)
  const propose = useMutation({ mutationFn: () => rulesApi.proposeHarness(repoId), onSuccess: set, onError: (e) => toast(e.message, { tone: 'err' }) })
  const fromRepo = useMutation({ mutationFn: () => rulesApi.harnessFromRepo(repoId), onSuccess: set, onError: (e) => toast(e.message, { tone: 'err' }) })
  const busy = propose.isPending || fromRepo.isPending
  return (
    <>
      <p className="text-sm text-slate-600 dark:text-slate-300">
        Antes de verificar las reglas con pruebas hace falta un arnés: un <code className="font-mono">conftest.py</code> con <code className="font-mono">api</code>,{' '}
        <code className="font-mono">como(rol)</code> y <code className="font-mono">crear_…()</code> para este proyecto. Se arma una vez y se valida con una prueba de humo.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {view.repo_harness && (
          <Button variant="secondary" onClick={() => fromRepo.mutate()} disabled={busy} title={view.repo_harness}>
            {fromRepo.isPending ? <Spinner className="w-4 h-4" /> : <Icon name="branch" className="w-4 h-4" />}
            Usar el del repositorio
          </Button>
        )}
        {view.can_generate && (
          <Button onClick={() => propose.mutate()} disabled={busy}>
            {propose.isPending ? <Spinner className="w-4 h-4" /> : <Icon name="wand" className="w-4 h-4" />}
            Proponer con IA
          </Button>
        )}
      </div>
      {view.repo_harness && (
        <p className="mt-2 text-xs text-slate-400">
          El repositorio ya trae uno en <code className="font-mono">{view.repo_harness}</code>.
        </p>
      )}
      {propose.isPending && (
        <p className="mt-2 flex items-center gap-2 text-sm text-slate-500">
          <Spinner className="w-4 h-4" />
          La IA está leyendo el mapa y el código del proyecto… puede tardar hasta un minuto.
        </p>
      )}
      {!view.can_generate && !view.repo_harness && view.map?.framework && <p className="mt-2 text-sm text-slate-500">Configura GEMINI_API_KEY para que la IA proponga el arnés.</p>}
    </>
  )
}

/** Configuración → Reglas de negocio → Mapa y arnés de pruebas (docs/PROPUESTA_REGLAS_VERIFICABLES.md §6.2 y §7). */
export function HarnessCard({ repoId }: { repoId: string }) {
  const { data, error, refetch } = useHarness(repoId)
  return (
    <Card className="p-5 sm:p-6">
      <h2 className="font-semibold mb-3">Mapa y arnés de pruebas</h2>
      {error ? (
        <ErrorState error={error} onRetry={() => void refetch()} />
      ) : !data ? (
        <Spinner className="w-5 h-5" />
      ) : !data.cloned || !data.map ? (
        <p className="text-sm text-slate-500">Analiza el repositorio para que IA voy lea su código (endpoints, modelos y roles).</p>
      ) : (
        <div className="space-y-4">
          <MapLine map={data.map} />
          {data.map.framework && (
            <div className="border-t border-slate-200 dark:border-slate-800 pt-4">
              {/* key: al proponer otro arnés, el editor se reinicia con su código */}
              {data.harness ? <Editor key={data.harness.updated_at} repoId={repoId} view={data} harness={data.harness} /> : <Start repoId={repoId} view={data} />}
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
