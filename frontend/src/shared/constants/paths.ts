const withQuery = (base: string, query: Record<string, string | number | boolean | undefined>) => {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== false && v !== '') q.set(k, String(v))
  const qs = q.toString()
  return qs ? `${base}?${qs}` : base
}

/** Constructores de URL. Usar siempre estos en lugar de strings sueltos. */
export const paths = {
  login: () => '/login',
  dashboard: () => '/dashboard',
  analyze: (prefill?: { url?: string; branch?: string }) => withQuery('/analyze', { ...prefill }),
  job: (jobId: string) => `/analyze/jobs/${jobId}`,
  repos: () => '/repos',
  files: (repoId: string, file?: string) => withQuery(`/repos/${repoId}/files`, { file }),
  settings: (repoId: string) => `/repos/${repoId}/settings`,
  team: () => '/team',
  joinTeam: (code: string) => `/join/${code}`,
  /** Redirect URI de la OAuth App de GitHub */
  githubCallback: () => '/github/callback',
}
