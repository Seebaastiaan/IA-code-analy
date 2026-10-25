import { NavLink, useLocation } from 'react-router'
import { useSelectedRepo } from '@/features/repos/store/selectedRepo.store'
import { useHealth } from '@/features/settings'
import { Icon } from '@/shared/ui'
import { cn } from '@/shared/utils/cn'
import { NAV } from './navigation'

function ServiceStatus() {
  const { data } = useHealth()
  const sandbox = data?.services.find((s) => s.id === 'sandbox')
  const tunnelUp = data?.services.find((s) => s.id === 'tunnel')?.status === 'ok'

  return (
    <div className="p-4 border-t border-slate-200 dark:border-slate-800 space-y-2 text-xs">
      <div className="flex items-center gap-2">
        <span className="relative flex w-2 h-2">
          {tunnelUp && <span className="absolute inline-flex w-full h-full rounded-full bg-emerald-400 opacity-75 animate-ping" />}
          <span className={cn('relative w-2 h-2 rounded-full', tunnelUp ? 'bg-emerald-500' : 'bg-slate-400')} />
        </span>
        <span className="text-slate-600 dark:text-slate-300">{tunnelUp ? 'Túnel activo' : 'Túnel inactivo'}</span>
        <span className="ml-auto font-mono text-slate-400 truncate">{data?.tunnel_host ?? '—'}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className={cn('w-2 h-2 rounded-full', sandbox?.status === 'ok' ? 'bg-emerald-500' : 'bg-slate-400')} />
        <span className="text-slate-600 dark:text-slate-300 truncate">{sandbox?.name ?? 'Sandbox'}</span>
        {sandbox && <span className="ml-auto text-slate-400">{sandbox.label}</span>}
      </div>
    </div>
  )
}

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const repoId = useSelectedRepo((s) => s.repoId)
  const { pathname } = useLocation()

  return (
    <>
      <div className={cn('fixed inset-0 z-30 bg-slate-900/40 backdrop-blur-sm lg:hidden', !open && 'hidden')} onClick={onClose} />
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 w-64 lg:translate-x-0 transition-transform duration-200 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col',
          !open && '-translate-x-full',
        )}
      >
        <div className="h-16 flex items-center gap-3 px-5 border-b border-slate-200 dark:border-slate-800">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-fuchsia-500 grid place-items-center text-white font-extrabold text-sm shadow-lg shadow-brand-500/30">IA</div>
          <div className="leading-tight">
            <p className="font-bold tracking-tight">IA voy</p>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">Analizador de código Python</p>
          </div>
          <button type="button" className="ml-auto lg:hidden p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800" onClick={onClose} aria-label="Cerrar menú">
            <Icon name="x" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto scroll-thin px-3 py-4 space-y-5">
          {NAV.map((sec) => (
            <div key={sec.group}>
              <p className="px-3 mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">{sec.group}</p>
              {sec.items.map((item) => (
                <NavLink
                  key={item.id}
                  to={item.to(repoId)}
                  // Sin `end`, "Repositorios" (/repos) quedaría activo también en /repos/:id/files, etc.
                  end
                  onClick={onClose}
                  className={({ isActive }) =>
                    cn(
                      'w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition',
                      isActive || item.match?.(pathname)
                        ? 'bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300'
                        : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-200',
                    )
                  }
                >
                  <Icon name={item.icon} className="w-[18px] h-[18px]" />
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <ServiceStatus />
      </aside>
    </>
  )
}
