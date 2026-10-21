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
  /** reportId = 'latest' deja que el backend resuelva el último análisis */
  report: (repoId: string, reportId: string | number = 'latest', query: { tab?: string; q?: string; cat?: string; finding?: number } = {}) =>
    withQuery(`/repos/${repoId}/reports/${reportId}`, query),
  files: (repoId: string, file?: string) => withQuery(`/repos/${repoId}/files`, { file }),
  editor: (repoId: string, opts: { file?: string; line?: number; diff?: boolean } = {}) =>
    withQuery(`/repos/${repoId}/editor`, { file: opts.file, line: opts.line, diff: opts.diff ? 1 : undefined }),
  assistant: (repoId: string, question?: string) => withQuery(`/repos/${repoId}/assistant`, { q: question }),
  compare: (repoId: string) => `/repos/${repoId}/compare`,
  settings: (repoId: string) => `/repos/${repoId}/settings`,
  publicReport: (shareId: string) => `/r/${shareId}`,
  team: () => '/team',
  joinTeam: (code: string) => `/join/${code}`,
  /** Redirect URI de la OAuth App de GitHub */
  githubCallback: () => '/github/callback',
}
