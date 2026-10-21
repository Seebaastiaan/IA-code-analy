/** Estado del token de GitHub del usuario (lo guarda solo el backend al iniciar sesión con GitHub). */
export interface GithubStatus {
  connected: boolean
  login: string | null
  avatar_url: string | null
}

export interface GithubRepo {
  /** "equipo/api-pagos" */
  full_name: string
  html_url: string
  default_branch: string
  private: boolean
  description: string | null
  pushed_at: string
}

export interface GithubBranch {
  name: string
}
