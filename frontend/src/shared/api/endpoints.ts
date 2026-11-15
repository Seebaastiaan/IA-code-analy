/** Rutas del backend (ver docs/FRONTEND_SPEC.md §6). */
export const EP = {
  auth: {
    githubAuthorize: '/api/auth/github/authorize',
    githubCallback: '/api/auth/github/callback',
    logout: '/api/auth/logout',
    me: '/api/auth/me',
  },
  dashboard: '/api/dashboard',
  repos: {
    list: '/api/repos',
    history: (id: string) => `/api/repos/${id}/history`,
    analyze: (id: string) => `/api/repos/${id}/analyze`,
    tree: (id: string) => `/api/repos/${id}/tree`,
    index: (id: string) => `/api/repos/${id}/index`,
    analyses: (id: string) => `/api/repos/${id}/analyses`,
  },
  analyze: '/api/analyze',
  jobs: {
    get: (id: string) => `/api/jobs/${id}`,
    retry: (id: string) => `/api/jobs/${id}/retry`,
    socket: (id: string) => `/ws/jobs/${id}`,
  },
  report: {
    get: (id: string) => `/api/report/${id}`,
    share: (id: string) => `/api/report/${id}/share`,
    export: (id: string) => `/api/report/${id}/export`,
    /** Matriz regla → estado → evidencia de un análisis (id puede ser 'latest' con ?repo=) */
    rules: (id: string) => `/api/report/${id}/reglas`,
  },
  file: '/api/file',
  fix: '/api/fix',
  chat: '/api/chat',
  chatStream: '/api/chat/stream',
  diff: '/api/diff',
  config: (projectId: string) => `/api/projects/${projectId}/config`,
  /** Reglas de negocio: origen y carga desde Configuración (docs/adr/ADR-003) */
  rules: {
    project: (projectId: string) => `/api/projects/${projectId}/reglas`,
    /** Las reglas son de cada proyecto: se validan contra su repositorio y la plantilla lleva su nombre */
    validate: (projectId: string) => `/api/projects/${projectId}/reglas/validar`,
    template: (projectId: string) => `/api/projects/${projectId}/reglas/plantilla`,
  },
  github: {
    status: '/api/github/status',
    repos: '/api/github/repos',
    /** fullName = "owner/repo" */
    branches: (fullName: string) => `/api/github/repos/${fullName}/branches`,
  },
  health: '/api/health',
  team: {
    root: '/api/team',
    invites: '/api/team/invites',
    invite: (code: string) => `/api/team/invites/${code}`,
    join: '/api/team/join',
    member: (userId: string) => `/api/team/members/${userId}`,
    owner: (userId: string) => `/api/team/members/${userId}/owner`,
  },
  public: {
    get: (shareId: string) => `/api/public/r/${shareId}`,
    unlock: (shareId: string) => `/api/public/r/${shareId}/unlock`,
  },
} as const
