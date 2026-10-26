import { Link, useNavigate, useParams } from 'react-router'
import { ApiError } from '@/shared/api/errors'
import { paths } from '@/shared/constants/paths'
import { Button, buttonClass, Card, EmptyState, Icon, PageLoader, Spinner } from '@/shared/ui'
import { formatDateTime } from '@/shared/utils/format'
import { teamApi, useInvitePreview, useTeamMutation } from '../api/team.api'

/** /join/:code — vista previa de la invitación y confirmación antes de cambiar de equipo. */
export default function JoinTeamPage() {
  const { code = '' } = useParams()
  const navigate = useNavigate()
  const { data: invite, error, isPending } = useInvitePreview(code)
  const join = useTeamMutation(teamApi.join, { success: 'Te uniste al equipo', switchesTeam: true, onDone: () => navigate(paths.dashboard(), { replace: true }) })

  if (isPending) return <PageLoader />
  if (error || !invite) {
    const status = error instanceof ApiError ? error.status : 0
    return (
      <EmptyState icon={status === 410 ? 'clock' : 'alert'} title={status === 410 ? 'Esta invitación expiró' : 'Esta invitación no existe'}>
        <p>Pide a quien administra el equipo un enlace nuevo.</p>
      </EmptyState>
    )
  }

  return (
    <div className="min-h-[60vh] grid place-items-center">
      <Card className="p-6 sm:p-8 w-full max-w-md text-center">
        <span className="mx-auto w-12 h-12 rounded-2xl bg-brand-100 dark:bg-brand-500/15 text-brand-600 dark:text-brand-300 grid place-items-center">
          <Icon name="users" />
        </span>
        <p className="text-sm text-slate-500 mt-4">{invite.invited_by} te invitó a</p>
        <h1 className="text-xl font-bold mt-1">{invite.team_name}</h1>
        <p className="text-sm text-slate-500 mt-1">
          {invite.members} miembro(s) · la invitación vence el {formatDateTime(invite.expires_at)}
        </p>
        {invite.already_member ? (
          <>
            <p className="text-sm mt-5">Ya eres parte de este equipo.</p>
            <Link to={paths.dashboard()} className={buttonClass('primary', 'w-full mt-4')}>
              Ir al tablero
            </Link>
          </>
        ) : (
          <>
            {invite.conflicts.length > 0 && (
              <div className="mt-5 text-left rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/20 px-4 py-3 text-sm text-amber-800 dark:text-amber-200">
                El equipo ya tiene {invite.conflicts.length === 1 ? 'este repositorio' : 'estos repositorios'}; tus análisis de {invite.conflicts.length === 1 ? 'él' : 'ellos'} se
                descartan y verás los del equipo: <span className="font-mono">{invite.conflicts.join(', ')}</span>
              </div>
            )}
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-5">
              Al unirte verás los repositorios, reportes y configuración del equipo, y tus repositorios pasarán a ser del equipo.
            </p>
            <Button className="w-full mt-4" onClick={() => join.mutate(code)} disabled={join.isPending}>
              {join.isPending && <Spinner />}
              Unirme al equipo
            </Button>
            <Link to={paths.dashboard()} className={buttonClass('ghost', 'w-full mt-2 justify-center')}>
              Ahora no
            </Link>
          </>
        )}
      </Card>
    </div>
  )
}
