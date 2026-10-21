import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { authApi, useSession } from '@/features/auth'
import { EP } from '@/shared/api/endpoints'
import { http } from '@/shared/api/http'
import { toast } from '@/shared/hooks/useToast'
import type { InvitePreview, Team, TeamInvite } from '../types'

export const teamApi = {
  get: () => http.get<Team>(EP.team.root),
  rename: (name: string) => http.patch<Team>(EP.team.root, { name }),
  invite: () => http.post<TeamInvite>(EP.team.invites),
  preview: (code: string) => http.get<InvitePreview>(EP.team.invite(code)),
  join: (code: string) => http.post<Team>(EP.team.join, { code }),
  remove: (userId: string) => http.delete<Team>(EP.team.member(userId)),
  leave: () => http.delete<Team>(EP.team.member('me')),
  transfer: (userId: string) => http.post<Team>(EP.team.owner(userId)),
}

export const TEAM_KEY = ['team'] as const

export const useTeam = () => useQuery({ queryKey: TEAM_KEY, queryFn: teamApi.get })

export const useInvitePreview = (code: string) => useQuery({ queryKey: ['team-invite', code], queryFn: () => teamApi.preview(code), retry: false })

/**
 * Cambio en el equipo. Si cambia de qué equipo soy (unirme, salir), cambian los repos que veo: se
 * descarta toda la caché y se actualiza el usuario (el header muestra el equipo).
 */
export function useTeamMutation<A>(fn: (arg: A) => Promise<Team>, opts: { success: string; switchesTeam?: boolean; onDone?: (team: Team) => void }) {
  const queryClient = useQueryClient()
  const setUser = useSession((s) => s.setUser)
  return useMutation({
    mutationFn: fn,
    onSuccess: async (team) => {
      if (opts.switchesTeam) await queryClient.invalidateQueries()
      queryClient.setQueryData(TEAM_KEY, team)
      setUser(await authApi.me())
      toast(opts.success)
      opts.onDone?.(team)
    },
    onError: (e) => toast(e.message, { tone: 'err' }),
  })
}
