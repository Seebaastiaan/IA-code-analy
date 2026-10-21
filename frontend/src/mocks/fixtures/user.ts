import type { User } from '@/features/auth'

export const demoUser: User = {
  id: 'u1',
  name: 'Ana López',
  initials: 'AL',
  email: 'ana@equipo.dev',
  team: { name: 'Equipo Backend', members: 6 },
  login: 'ana-lopez',
  avatar_url: null,
}
