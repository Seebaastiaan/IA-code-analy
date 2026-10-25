import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useSession } from '@/features/auth'
import { toast } from '@/shared/hooks/useToast'
import { Button, Card, Chip, ErrorState, Icon, Input, Label, PageHeader, PageLoader, Spinner } from '@/shared/ui'
import { formatDateTime, timeAgo } from '@/shared/utils/format'
import { teamApi, useTeam, useTeamMutation } from '../api/team.api'
import type { Team, TeamInvite, TeamMember } from '../types'

/** Acción destructiva en dos clics: el primero pide confirmación (sin diálogos del navegador). */
function ConfirmButton({ label, confirm, onConfirm, disabled }: { label: string; confirm: string; onConfirm: () => void; disabled?: boolean }) {
  const [asking, setAsking] = useState(false)
  return asking ? (
    <span className="flex gap-1">
      <Button variant="ghost" className="text-rose-600 dark:text-rose-400" onClick={onConfirm} disabled={disabled}>
        {confirm}
      </Button>
      <Button variant="ghost" onClick={() => setAsking(false)}>
        Cancelar
      </Button>
    </span>
  ) : (
    <Button variant="ghost" onClick={() => setAsking(true)} disabled={disabled}>
      {label}
    </Button>
  )
}

function Avatar({ m }: { m: TeamMember }) {
  return m.avatar_url ? (
    <img src={m.avatar_url} alt="" className="w-9 h-9 rounded-lg" />
  ) : (
    <span className="w-9 h-9 rounded-lg bg-gradient-to-br from-sky-400 to-brand-500 text-white text-xs font-bold grid place-items-center">
      {m.name.slice(0, 2).toUpperCase()}
    </span>
  )
}

function RenameForm({ team }: { team: Team }) {
  const [name, setName] = useState(team.name)
  const rename = useTeamMutation(teamApi.rename, { success: 'Nombre del equipo actualizado' })
  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    rename.mutate(name.trim())
  }
  return (
    <form onSubmit={onSubmit} className="flex gap-2 items-end">
      <div className="flex-1">
        <Label htmlFor="team-name">Nombre del equipo</Label>
        <Input id="team-name" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
      </div>
      <Button type="submit" variant="secondary" disabled={!name.trim() || name.trim() === team.name || rename.isPending}>
        {rename.isPending && <Spinner />}
        Guardar
      </Button>
    </form>
  )
}

function InviteCard() {
  const [invite, setInvite] = useState<TeamInvite | null>(null)
  const create = useMutation({ mutationFn: teamApi.invite, onSuccess: setInvite, onError: (e) => toast(e.message, { tone: 'err' }) })
  const copy = async () => {
    if (!invite) return
    try {
      await navigator.clipboard.writeText(invite.url)
      toast('Enlace copiado al portapapeles')
    } catch {
      toast(`Enlace: ${invite.url}`, { tone: 'info' })
    }
  }
  return (
    <Card className="p-5">
      <h2 className="font-semibold">Invitar al equipo</h2>
      <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 mb-4">
        Comparte el enlace: quien lo abra (con su cuenta de GitHub) entra al equipo y ve sus repositorios. Vale 7 días y para varias personas.
      </p>
      {invite ? (
        <>
          <Label htmlFor="invite-url">Enlace de invitación</Label>
          <div className="flex gap-2">
            <Input id="invite-url" readOnly value={invite.url} className="font-mono text-xs" />
            <Button variant="secondary" onClick={copy}>
              <Icon name="copy" className="w-4 h-4" />
              Copiar
            </Button>
          </div>
          <p className="text-xs text-slate-400 mt-2">Expira el {formatDateTime(invite.expires_at)}</p>
        </>
      ) : (
        <Button onClick={() => create.mutate()} disabled={create.isPending}>
          {create.isPending ? <Spinner /> : <Icon name="plus" className="w-4 h-4" />}
          Crear enlace de invitación
        </Button>
      )}
    </Card>
  )
}

export default function TeamPage() {
  const { data: team, error, refetch } = useTeam()
  const me = useSession((s) => s.user)
  const remove = useTeamMutation(teamApi.remove, { success: 'Se quitó a la persona del equipo' })
  const transfer = useTeamMutation(teamApi.transfer, { success: 'Ahora administra el equipo otra persona' })
  const leave = useTeamMutation(() => teamApi.leave(), { success: 'Saliste del equipo', switchesTeam: true })

  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />
  if (!team) return <PageLoader />
  const owner = team.role === 'owner'
  const alone = team.members.length === 1

  return (
    <>
      <PageHeader title={team.name} eyebrow="Equipo" subtitle={`${team.members.length} miembro(s) · ${team.repos} repositorio(s) conectados al equipo`} />
      <div className="grid lg:grid-cols-[1fr_22rem] gap-4 items-start">
        <Card className="overflow-hidden">
          <div className="p-5 border-b border-slate-200 dark:border-slate-800">
            <h2 className="font-semibold">Miembros</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Todos ven y analizan los mismos repositorios, reportes y configuración.</p>
          </div>
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {team.members.map((m) => (
              <li key={m.id} className="px-5 py-3 flex flex-wrap items-center gap-3">
                <Avatar m={m} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium truncate">
                    {m.name}
                    {m.id === me?.id && <span className="text-slate-400 font-normal"> (tú)</span>}
                  </p>
                  <p className="text-xs text-slate-500">
                    @{m.login} · se unió {timeAgo(m.joined_at)}
                  </p>
                </div>
                <Chip tone={m.role === 'owner' ? 'brand' : 'neutral'}>{m.role === 'owner' ? 'Administra' : 'Miembro'}</Chip>
                {owner && m.id !== me?.id && (
                  <span className="flex gap-1">
                    <ConfirmButton label="Ceder" confirm="Sí, cederle el equipo" onConfirm={() => transfer.mutate(m.id)} disabled={transfer.isPending} />
                    <ConfirmButton label="Quitar" confirm={`Sí, quitar a ${m.name.split(' ')[0]}`} onConfirm={() => remove.mutate(m.id)} disabled={remove.isPending} />
                  </span>
                )}
              </li>
            ))}
          </ul>
          {!alone && (
            <div className="p-5 border-t border-slate-200 dark:border-slate-800 flex flex-wrap items-center gap-3">
              <p className="text-sm text-slate-500 dark:text-slate-400 flex-1">
                {owner ? 'Para salir, primero cede el equipo a otra persona.' : 'Si sales, vuelves a un equipo propio sin repositorios.'}
              </p>
              {!owner && <ConfirmButton label="Salir del equipo" confirm="Sí, salir" onConfirm={() => leave.mutate(undefined)} disabled={leave.isPending} />}
            </div>
          )}
        </Card>
        <div className="space-y-4">
          {owner && (
            <Card className="p-5">
              <RenameForm team={team} />
            </Card>
          )}
          {owner ? (
            <InviteCard />
          ) : (
            <Card className="p-5">
              <h2 className="font-semibold">Invitar al equipo</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Pide a quien administra el equipo un enlace de invitación.</p>
            </Card>
          )}
        </div>
      </div>
    </>
  )
}
