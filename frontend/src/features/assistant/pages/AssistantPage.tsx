import { useMutation } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { useReport } from '@/features/report'
import { Button, Card, Chip, Icon, Input } from '@/shared/ui'
import { chatApi, useIndexInfo } from '../api/chat.api'
import { ChatMessageItem, TypingIndicator } from '../components/ChatMessageItem'
import { buildSuggestions } from '../constants/suggestions'
import { useChatStore } from '../store/chat.store'
import type { ChatMessage, HistoryTurn, IndexInfo } from '../types'

const EMPTY: ChatMessage[] = []
/** Turnos anteriores que se mandan con cada pregunta (el backend usa como máximo 8) */
const HISTORY_TURNS = 8

function welcomeText(index: IndexInfo, repoName: string): string {
  switch (index.status) {
    case 'building':
      return `Estoy indexando **${repoName}** para poder responder sobre su código. Tarda unos segundos; mientras tanto ya puedo responder sobre el reporte.`
    case 'not_configured':
      return 'El asistente no está configurado en el servidor: falta `GEMINI_API_KEY` en `backend/.env`.'
    case 'error':
      return `No pude indexar el código de **${repoName}**${index.error ? ` (${index.error})` : ''}. Lo reintento en un minuto; mientras tanto puedo responder sobre el reporte y sus hallazgos.`
    case 'not_cloned':
      return `El código de **${repoName}** no está disponible. Vuelve a analizar el repositorio para poder preguntar sobre él.`
    default:
      return `Hola, ya indexé **${repoName}**: ${index.py_files} archivos .py${index.readme ? ', el README' : ''}${index.report_num ? ` y el reporte #${index.report_num}` : ''}. Pregúntame sobre el código o sobre cualquier hallazgo.`
  }
}

export default function AssistantPage() {
  const { repoId = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const { data: report } = useReport(repoId)
  const { data: index } = useIndexInfo(repoId)
  const messages = useChatStore((s) => s.byRepo[repoId] ?? EMPTY)
  const add = useChatStore((s) => s.add)
  const update = useChatStore((s) => s.update)
  const [input, setInput] = useState('')
  const boxRef = useRef<HTMLDivElement>(null)
  // Sin clave del modelo o sin clon, cualquier pregunta fallaría: se bloquea la entrada y se explica por qué
  const unavailable = index?.status === 'not_configured' || index?.status === 'not_cloned'
  const suggestions = useMemo(() => buildSuggestions(report), [report])

  // La respuesta llega por streaming (SSE): el mensaje aparece con el primer trozo y crece hasta la respuesta final
  const ask = useMutation({
    mutationFn: async ({ message, history }: { message: string; history: HistoryTurn[] }) => {
      let id: number | null = null
      const write = (patch: Partial<ChatMessage>) => {
        if (id === null) id = add(repoId, { role: 'ai', content: '', ...patch })
        else update(repoId, id, patch)
      }
      try {
        const res = await chatApi.askStream({ repo_id: repoId, message, history }, (text) => {
          if (id === null) id = add(repoId, { role: 'ai', content: text, streaming: true })
          else update(repoId, id, (m) => ({ content: m.content + text }))
        })
        write({ content: res.content, sources: res.sources, action: res.action, model: res.model, streaming: false })
      } catch (e) {
        write({ content: `No pude responder: ${(e as Error).message}`, error: true, streaming: false })
      }
    },
  })
  const streaming = messages.at(-1)?.streaming === true
  // El scroll sigue a la respuesta mientras crece
  const lastLength = messages.at(-1)?.content.length ?? 0

  const send = (q: string) => {
    const text = q.trim()
    if (!text || ask.isPending || unavailable) return
    // Conversación previa (sin los mensajes de error) para que entienda "¿y cómo lo pruebo?"
    const history = messages
      .filter((m) => !m.error)
      .slice(-HISTORY_TURNS)
      .map((m): HistoryTurn => ({ role: m.role === 'me' ? 'user' : 'model', content: m.content }))
    add(repoId, { role: 'me', content: text })
    ask.mutate({ message: text, history })
    setInput('')
  }

  // ?q= llega desde "Preguntar a la IA" en un hallazgo: se envía una sola vez
  const initial = params.get('q')
  const sentInitial = useRef<string | null>(null)
  useEffect(() => {
    // Espera a saber si el asistente está disponible antes de enviarla
    // Si no está disponible no se envía: el mensaje de bienvenida explica por qué
    if (!initial || !index || unavailable || sentInitial.current === initial) return
    sentInitial.current = initial
    send(initial)
    setParams(
      (p) => {
        p.delete('q')
        return p
      },
      { replace: true },
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial, index === undefined, index?.status])

  useEffect(() => {
    if (boxRef.current) boxRef.current.scrollTop = boxRef.current.scrollHeight
  }, [messages.length, lastLength, ask.isPending])

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    send(input)
  }

  const model = messages.findLast((m) => m.model)?.model ?? index?.model ?? 'Modelo IA'
  const welcome = index ? welcomeText(index, report?.repo_name ?? 'el repositorio') : null

  const suggestionButtons = (cls: string) =>
    suggestions.map((s) => (
      <button key={s} type="button" onClick={() => send(s)} disabled={ask.isPending || unavailable} className={cls}>
        {s}
      </button>
    ))

  return (
    <div className="grid lg:grid-cols-[1fr_18rem] gap-4 h-[calc(100vh-8.5rem)] min-h-[520px]">
      <Card className="flex flex-col overflow-hidden min-h-0">
        <div className="px-4 sm:px-5 py-3.5 border-b border-slate-200 dark:border-slate-800 flex items-center gap-3">
          <span className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-fuchsia-500 text-white grid place-items-center">
            <Icon name="sparkle" className="w-4 h-4" />
          </span>
          <div className="min-w-0">
            <p className="font-semibold text-sm">Asistente de código</p>
            <p className="text-xs text-slate-400 truncate">
              {report?.repo_name ?? '…'}
              {report && ` · reporte #${report.num}`}
            </p>
          </div>
          <Chip tone={unavailable ? 'neutral' : 'success'} className="ml-auto shrink-0">
            <span className={unavailable ? 'w-1.5 h-1.5 rounded-full bg-slate-400' : 'w-1.5 h-1.5 rounded-full bg-emerald-500'} />
            {index?.status === 'not_configured' ? 'Sin configurar' : model}
          </Chip>
        </div>

        <div ref={boxRef} className="flex-1 overflow-y-auto scroll-thin p-4 sm:p-5 space-y-4" aria-live="polite">
          {welcome && <ChatMessageItem message={{ id: 0, role: 'ai', content: welcome }} repoId={repoId} findings={[]} />}
          {messages.map((m) => (
            <ChatMessageItem key={m.id} message={m} repoId={repoId} findings={report?.findings ?? []} />
          ))}
          {ask.isPending && !streaming && <TypingIndicator />}
        </div>

        <div className="p-3 sm:p-4 border-t border-slate-200 dark:border-slate-800">
          <div className="flex gap-2 overflow-x-auto scroll-thin pb-2 lg:hidden">
            {suggestionButtons('shrink-0 rounded-full border border-slate-200 dark:border-slate-700 px-3 py-1 text-xs hover:border-brand-400 disabled:opacity-50')}
          </div>
          <form onSubmit={onSubmit} className="flex gap-2">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              autoComplete="off"
              maxLength={2000}
              disabled={unavailable}
              placeholder={unavailable ? 'El asistente no está disponible para este repositorio' : 'Pregunta sobre el código o un hallazgo…'}
              aria-label="Pregunta"
            />
            <Button type="submit" className="px-3.5" aria-label="Enviar" disabled={ask.isPending || unavailable || !input.trim()}>
              <Icon name="send" className="w-4 h-4" />
            </Button>
          </form>
        </div>
      </Card>

      <aside className="hidden lg:flex flex-col gap-4">
        <Card className="p-5">
          <h2 className="font-semibold text-sm mb-3">Contexto indexado</h2>
          <dl className="grid grid-cols-2 gap-3">
            {[
              [index?.py_files ?? '—', 'archivos .py'],
              [index?.chunks ?? '—', 'fragmentos'],
              [index ? (index.readme ? 1 : 0) : '—', 'README'],
              [index?.report_num ? `#${index.report_num}` : '—', 'reporte'],
            ].map(([a, b]) => (
              <div key={String(b)} className="rounded-xl bg-slate-50 dark:bg-slate-950 p-3">
                <dt className="text-lg font-bold">{a}</dt>
                <dd className="text-xs text-slate-500">{b}</dd>
              </div>
            ))}
          </dl>
          {index && <p className="text-xs text-slate-400 mt-3">Respaldo: {index.fallback} si {index.model} no está disponible.</p>}
        </Card>
        <Card className="p-5">
          <h2 className="font-semibold text-sm mb-3">Prueba preguntar</h2>
          <div className="space-y-2">
            {suggestionButtons('w-full text-left rounded-xl border border-slate-200 dark:border-slate-800 px-3 py-2 text-sm hover:border-brand-400 hover:bg-brand-50/50 dark:hover:bg-brand-500/5 transition disabled:opacity-50')}
          </div>
        </Card>
      </aside>
    </div>
  )
}
