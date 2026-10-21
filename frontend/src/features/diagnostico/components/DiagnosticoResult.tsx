import { CategoryChip, Card, Chip, Icon, ScoreRing, Select, SeverityBadge } from '@/shared/ui'
import type { DiagnosticoResponse } from '../types'

const ORDER = { alta: 0, media: 1, baja: 2 } as const

interface DiagnosticoResultProps {
  result: DiagnosticoResponse
  busy: boolean
  onFile: (file: string) => void
}

/** Lo que respondió la IA: score sugerido, resumen y hallazgos con su línea. */
export function DiagnosticoResult({ result: r, busy, onFile }: DiagnosticoResultProps) {
  const hallazgos = [...r.diagnostico.hallazgos].sort((a, b) => ORDER[a.severidad] - ORDER[b.severidad])

  return (
    <Card className="mt-4 overflow-hidden">
      <div className="p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center gap-5 border-b border-slate-200 dark:border-slate-800">
        <ScoreRing value={r.diagnostico.score} size={96} stroke={9} />
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <h2 className="text-xl font-bold tracking-tight break-all">{r.repo}</h2>
            <Chip>
              <Icon name="branch" className="w-3 h-3" />
              {r.branch}
            </Chip>
            <Chip tone="brand">
              <Icon name="sparkle" className="w-3 h-3" />
              {r.model}
            </Chip>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Commit <span className="font-mono">{r.commit}</span>
          </p>
          <p className="text-sm mt-2">{r.diagnostico.resumen}</p>
        </div>
        <div className="sm:w-64">
          <label htmlFor="d-pick" className="block text-xs font-medium text-slate-500 mb-1">
            Archivo diagnosticado
          </label>
          <Select id="d-pick" value={r.file} disabled={busy} onChange={(e) => onFile(e.target.value)} className="font-mono text-xs">
            {r.files.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </Select>
        </div>
      </div>
      <div className="px-5 py-2 text-xs text-slate-400 bg-slate-50/60 dark:bg-slate-950/40 border-b border-slate-100 dark:border-slate-800">
        {hallazgos.length} hallazgo(s) · el score lo sugiere la IA y puede variar entre corridas
      </div>
      <ul className="divide-y divide-slate-100 dark:divide-slate-800">
        {hallazgos.map((h, i) => (
          <li key={i} className="px-5 py-3.5 flex flex-col sm:flex-row gap-2 sm:gap-4">
            <div className="flex items-center gap-2 sm:w-52 shrink-0">
              <SeverityBadge sev={h.severidad} />
              <span className="font-mono text-xs text-slate-500 truncate">{h.regla}</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium">{h.mensaje}</p>
              <p className="text-xs text-slate-500 mt-0.5">{h.recomendacion}</p>
              <p className="text-xs font-mono text-slate-400 mt-0.5">
                {r.file}:{h.linea}
              </p>
            </div>
            <div className="shrink-0">
              <CategoryChip cat={h.categoria} />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}
