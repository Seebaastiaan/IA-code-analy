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
  },
  file: '/api/file',
  fix: '/api/fix',
  chat: '/api/chat',
  chatStream: '/api/chat/stream',
  diff: '/api/diff',
  config: (projectId: string) => `/api/projects/${projectId}/config`,
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
