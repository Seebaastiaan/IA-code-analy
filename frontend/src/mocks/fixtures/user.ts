import type { User } from '@/features/auth'

const base: User = {
  id: 'u1',
  name: 'Ana López',
  initials: 'AL',
  email: 'ana@equipo.dev',
  team: { name: 'Equipo IA VOY', members: 11 },
  login: 'ana-lopez',
  avatar_url: null,
}

/** Usuario de la sesión simulada; `localStorage['iavoy-mock-user'] = "Nombre Apellido"` lo cambia (capturas por persona). */
function storedName(): string | null {
  try {
    return localStorage.getItem('iavoy-mock-user')?.trim() || null
  } catch {
    return null
  }
}

/** La sesión simulada es de un integrante con nombre (capturas): el equipo muestra a los integrantes reales. */
export const customUser = storedName() !== null

function fromStorage(): User {
  try {
    const name = storedName()
    if (!name) return base
    const parts = name.split(/\s+/)
    const initials = (parts[0][0] + (parts[1]?.[0] ?? '')).toUpperCase()
    const login = parts.slice(0, 2).join('-').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
    return { ...base, name, initials, login, email: `${login}@equipo.dev` }
  } catch {
    return base
  }
}

export const demoUser: User = fromStorage()
