export type TeamRole = 'owner' | 'member'

export interface TeamMember {
  id: string
  name: string
  login: string
  avatar_url: string | null
  role: TeamRole
  joined_at: string
}

export interface Team {
  id: string
  name: string
  /** Mi rol en el equipo */
  role: TeamRole
  members: TeamMember[]
  repos: number
}

export interface TeamInvite {
  code: string
  url: string
  expires_at: string
}

export interface InvitePreview {
  team_name: string
  members: number
  invited_by: string
  expires_at: string
  already_member: boolean
  /** Repos propios que se descartan al unirse porque el equipo ya los tiene */
  conflicts: string[]
}
