import { EP } from '@/shared/api/endpoints'
import { http } from '@/shared/api/http'
import type { GithubAuthorizeResponse, GithubCallbackRequest, LoginResponse, User } from '../types'

export const authApi = {
  githubAuthorize: () => http.post<GithubAuthorizeResponse>(EP.auth.githubAuthorize, undefined, { anonymous: true }),
  githubCallback: (body: GithubCallbackRequest) => http.post<LoginResponse>(EP.auth.githubCallback, body, { anonymous: true }),
  logout: () => http.post<void>(EP.auth.logout),
  me: () => http.get<User>(EP.auth.me),
}
