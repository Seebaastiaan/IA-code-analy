export interface User {
  id: string
  name: string
  initials: string
  email: string
  team: { name: string; members: number }
  /** Usuario de GitHub (la cuenta de GitHub es la cuenta de la app) */
  login?: string
  avatar_url?: string | null
}

export interface LoginResponse {
  token: string
  user: User
}

/** URL de autorización de GitHub y el `state` que el frontend comprueba al volver. */
export interface GithubAuthorizeResponse {
  url: string
  state: string
}

/** Lo que GitHub devuelve en la redirección a /github/callback. */
export interface GithubCallbackRequest {
  code: string
  state: string
}
