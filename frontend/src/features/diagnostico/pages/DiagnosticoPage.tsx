import { useState } from 'react'
import { toast } from '@/shared/hooks/useToast'
import { EmptyState, PageHeader, ThemeToggle } from '@/shared/ui'
import { useDiagnostico } from '../api/diagnostico.api'
import { DiagnosticoForm } from '../components/DiagnosticoForm'
import { DiagnosticoResult } from '../components/DiagnosticoResult'
import type { DiagnosticoRequest } from '../types'

/** Prototipo del Sprint 3: la IA diagnostica un archivo de un repositorio clonado. */
export default function DiagnosticoPage() {
  const diagnostico = useDiagnostico()
  const [last, setLast] = useState<DiagnosticoRequest | null>(null)

  const run = (body: DiagnosticoRequest) => {
    setLast(body)
    diagnostico.mutate(body, { onError: (e) => toast(e.message, { tone: 'err' }) })
  }

  return (
    <div className="min-h-screen">
      <header className="h-16 border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-950/80 backdrop-blur">
        <div className="h-full max-w-5xl mx-auto px-4 sm:px-6 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-fuchsia-500 grid place-items-center text-white font-extrabold text-sm">IA</div>
          <div className="leading-tight">
            <p className="font-bold tracking-tight">IA voy</p>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">Analizador de código Python</p>
          </div>
          <ThemeToggle className="ml-auto" />
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8">
        <PageHeader title="Diagnóstico con IA" subtitle="Clona un repositorio de GitHub y pide a la IA un diagnóstico de uno de sus archivos." />
        <DiagnosticoForm busy={diagnostico.isPending} onSubmit={run} />
        {diagnostico.data ? (
          <DiagnosticoResult result={diagnostico.data} busy={diagnostico.isPending} onFile={(file) => last && run({ ...last, file })} />
        ) : (
          !diagnostico.isPending && (
            <EmptyState icon="sparkle" title="Aún no hay diagnóstico">
              <p>Escribe la URL de un repositorio público y elige la rama.</p>
            </EmptyState>
          )
        )}
      </main>
    </div>
  )
}
