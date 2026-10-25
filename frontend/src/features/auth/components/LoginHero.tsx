import { Icon, type IconName } from '@/shared/ui'

// Lo que hace la app en el Sprint 4; los analizadores y el score llegan en los siguientes sprints
const FEATURES: { icon: IconName; label: string; desc: string }[] = [
  { icon: 'branch', label: 'Clonado desde GitHub', desc: 'Repos públicos y privados de tu cuenta' },
  { icon: 'shield', label: 'Entorno aislado', desc: 'uv venv en WSL2 o Docker' },
  { icon: 'folder', label: 'Repositorios del equipo', desc: 'Cada análisis queda guardado en su historial' },
]

export function LoginHero() {
  return (
    <div className="hidden lg:flex relative overflow-hidden bg-gradient-to-br from-brand-600 via-brand-700 to-fuchsia-700 text-white p-12 flex-col justify-between">
      <div className="absolute -left-20 -bottom-20 w-96 h-96 rounded-full bg-fuchsia-400/30 blur-3xl" />
      <div className="absolute right-0 top-10 w-72 h-72 rounded-full bg-white/10 blur-3xl" />
      <div className="relative flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-white/15 grid place-items-center font-extrabold">IA</div>
        <span className="text-xl font-bold">IA voy</span>
      </div>
      <div className="relative">
        <h2 className="text-4xl font-extrabold tracking-tight leading-tight">
          Calidad de código Python,
          <br />
          medida y explicada.
        </h2>
        <div className="mt-8 space-y-3">
          {FEATURES.map((f) => (
            <div key={f.label} className="flex items-center gap-3 rounded-2xl bg-white/10 backdrop-blur px-4 py-3">
              <span className="w-9 h-9 rounded-xl bg-white/15 grid place-items-center">
                <Icon name={f.icon} className="w-4 h-4" />
              </span>
              <div>
                <p className="font-semibold text-sm">{f.label}</p>
                <p className="text-xs text-white/70">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
      <p className="relative text-xs text-white/60">Proyecto académico · 2026</p>
    </div>
  )
}
