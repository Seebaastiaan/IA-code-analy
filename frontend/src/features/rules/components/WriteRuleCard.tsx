import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from '@/shared/hooks/useToast'
import { Button, Card, Icon, Spinner } from '@/shared/ui'
import { projectRulesQuery, rulesApi } from '../api/rules.api'

/** «Escribe una regla con tus palabras» (docs/PLAN_REGLAS_AUTOMATICO.md, paso 5): la IA la redacta y entra en borrador. */
export function WriteRuleCard({ repoId, canWrite }: { repoId: string; canWrite?: boolean }) {
  const queryClient = useQueryClient()
  const [text, setText] = useState('')
  const write = useMutation({
    mutationFn: () => rulesApi.writeRule(repoId, text),
    onSuccess: (saved) => {
      queryClient.setQueryData(projectRulesQuery(repoId).queryKey, saved)
      setText('')
      toast(saved.messages?.[0] ?? 'Regla agregada en borrador')
    },
    onError: (e) => toast(e.message, { tone: 'err' }),
  })

  return (
    <Card className="p-5 sm:p-6">
      <h2 className="font-semibold">Escribe una regla con tus palabras</h2>
      <p className="mt-1 text-sm text-slate-500">
        Por ejemplo: «un descuento de más del 20% lo aprueba el gerente». La IA la convierte en una regla con ejemplos y te pregunta lo que falte; entra como borrador para que la apruebes.
      </p>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        maxLength={1000}
        rows={3}
        aria-label="Regla con tus palabras"
        className="mt-3 w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-transparent p-3 text-sm outline-none focus:border-brand-500 focus:ring-4 focus:ring-brand-500/15"
      />
      <div className="mt-2">
        <Button onClick={() => write.mutate()} disabled={!text.trim() || write.isPending || canWrite === false}>
          {write.isPending ? <Spinner className="w-4 h-4" /> : <Icon name="wand" className="w-4 h-4" />}
          Agregar la regla
        </Button>
      </div>
    </Card>
  )
}
