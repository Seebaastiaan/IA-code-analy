import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { EP } from '@/shared/api/endpoints'
import { http } from '@/shared/api/http'
import type { GithubBranch, GithubRepo, GithubStatus } from '../types'

export const githubApi = {
  status: () => http.get<GithubStatus>(EP.github.status),
  repos: (q: string) => http.get<GithubRepo[]>(EP.github.repos, { q: q || undefined }),
  branches: (fullName: string) => http.get<GithubBranch[]>(EP.github.branches(fullName)),
}

export const useGithubStatus = () => useQuery({ queryKey: ['github', 'status'], queryFn: githubApi.status })

/** Repos de la cuenta de GitHub; mantiene la lista anterior mientras se escribe la búsqueda. */
export const useGithubRepos = (q: string, enabled: boolean) =>
  useQuery({ queryKey: ['github', 'repos', q], queryFn: () => githubApi.repos(q), enabled, placeholderData: keepPreviousData })

export const useGithubBranches = (fullName: string | null) =>
  useQuery({ queryKey: ['github', 'branches', fullName], queryFn: () => githubApi.branches(fullName!), enabled: Boolean(fullName) })
