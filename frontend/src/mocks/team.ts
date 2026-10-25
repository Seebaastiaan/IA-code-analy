/** Equipo simulado (modo mock): "Equipo IA VOY" con 6 miembros, como en el prototipo. */
import type { InvitePreview, Team, TeamInvite, TeamMember } from '@/features/team/types'
import { customUser, demoUser } from './fixtures/user'

const DAY = 86_400_000
const ago = (days: number) => new Date(Date.now() - days * DAY).toISOString()

/** Integrantes del proyecto (Planeación v3): el equipo cuando la sesión es de uno de ellos. Andrea es la líder general. */
const PROJECT = [
  'Andrea Peña', 'Karen Peña', 'Emiliano Sánchez', 'Dylan Martínez', 'Carlos Jara', 'Ana Cristina Luciano',
  'Uriel Castorela', 'Marco Espino', 'Diego Salinas', 'Evelyn Martínez', 'Luis Gabriel Manzano',
]

const login = (name: string) => name.split(' ').slice(0, 2).join('-').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()

const projectMembers = (): TeamMember[] =>
  PROJECT.map((name, i) => ({
    id: name === demoUser.name ? demoUser.id : `p${i}`,
    name,
    login: login(name),
    avatar_url: null,
    role: i === 0 ? 'owner' : 'member',
    joined_at: ago(40 - i),
  }))

const team = {
  id: 't1',
  name: demoUser.team.name,
  members: customUser ? projectMembers() : ([
    { id: demoUser.id, name: demoUser.name, login: demoUser.login, avatar_url: null, role: 'owner', joined_at: ago(120) },
    { id: 'u2', name: 'Carlos Méndez', login: 'cmendez', avatar_url: null, role: 'member', joined_at: ago(110) },
    { id: 'u3', name: 'Lucía Torres', login: 'ltorres', avatar_url: null, role: 'member', joined_at: ago(95) },
    { id: 'u4', name: 'Diego Salinas', login: 'dsalinas', avatar_url: null, role: 'member', joined_at: ago(60) },
    { id: 'u5', name: 'Mariana Ruiz', login: 'mruiz', avatar_url: null, role: 'member', joined_at: ago(30) },
    { id: 'u6', name: 'Óscar Pérez', login: 'operez', avatar_url: null, role: 'member', joined_at: ago(7) },
  ] as TeamMember[]),
}

const invites = new Map<string, TeamInvite>()

const view = (): Team => ({
  id: team.id,
  name: team.name,
  role: team.members.find((m) => m.id === demoUser.id)?.role ?? 'member',
  members: [...team.members],
  repos: 5,
})

/** El usuario de la sesión simulada refleja el equipo (nombre y número de miembros). */
function sync() {
  demoUser.team = { name: team.name, members: team.members.length }
}

export const getTeam = view

export function rename(name: string) {
  team.name = name
  sync()
  return view()
}

export function createInvite(origin: string): TeamInvite {
  const code = Math.random().toString(36).slice(2, 10)
  const invite = { code, url: `${origin}/join/${code}`, expires_at: new Date(Date.now() + 7 * DAY).toISOString() }
  invites.set(code, invite)
  return invite
}

export function preview(code: string): InvitePreview | null {
  const invite = invites.get(code)
  if (!invite) return null
  return { team_name: team.name, members: team.members.length, invited_by: demoUser.name, expires_at: invite.expires_at, already_member: true, conflicts: [] }
}

export function remove(userId: string) {
  team.members = team.members.filter((m) => m.id !== userId)
  sync()
  return view()
}

export function transfer(userId: string) {
  team.members = team.members.map((m) => ({ ...m, role: m.id === userId ? 'owner' : 'member' }))
  return view()
}
