"""Cliente mínimo de la API de GitHub para el flujo OAuth y la lista de repos/ramas."""

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.config import Settings

OAUTH_URL = "https://github.com/login/oauth"
API_URL = "https://api.github.com"
SCOPES = "repo read:user user:email"


class GithubAuthError(Exception):
    """El token fue revocado o expiró en GitHub."""


class GithubError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@dataclass
class TokenGrant:
    access_token: str
    scope: str


@dataclass
class GithubUser:
    id: int
    login: str
    name: str | None
    email: str | None
    avatar_url: str | None


class GithubClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient):
        self.settings = settings
        self.http = http

    def authorize_url(self, state: str) -> str:
        query = {"client_id": self.settings.github_client_id, "redirect_uri": self.settings.github_redirect_uri, "scope": SCOPES, "state": state, "allow_signup": "false"}
        return f"{OAUTH_URL}/authorize?{urlencode(query)}"

    async def exchange_code(self, code: str) -> TokenGrant:
        res = await self.http.post(
            f"{OAUTH_URL}/access_token",
            headers={"Accept": "application/json"},
            data={"client_id": self.settings.github_client_id, "client_secret": self.settings.github_client_secret, "code": code, "redirect_uri": self.settings.github_redirect_uri},
        )
        data = res.json() if res.is_success else {}
        # GitHub responde 200 con {"error": "bad_verification_code"} cuando el code ya se usó o expiró
        if "access_token" not in data:
            raise GithubError(400, data.get("error_description") or "GitHub rechazó el código de autorización")
        return TokenGrant(access_token=data["access_token"], scope=data.get("scope", ""))

    async def _get(self, token: str, path: str, params: dict | None = None) -> httpx.Response:
        res = await self.http.get(f"{API_URL}{path}", params=params, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
        if res.status_code == 401:
            raise GithubAuthError()
        if not res.is_success:
            raise GithubError(res.status_code, res.json().get("message", res.reason_phrase) if res.content else res.reason_phrase)
        return res

    async def get_user(self, token: str) -> GithubUser:
        data = (await self._get(token, "/user")).json()
        email = data.get("email")
        if not email:
            # El correo público puede estar oculto; el principal verificado viene de /user/emails
            emails = (await self._get(token, "/user/emails")).json()
            email = next((e["email"] for e in emails if e.get("primary") and e.get("verified")), None)
        return GithubUser(id=data["id"], login=data["login"], name=data.get("name"), email=email, avatar_url=data.get("avatar_url"))

    async def list_repos(self, token: str) -> list[dict]:
        # Primera página (100 repos, los más recientes primero); la búsqueda filtra sobre ellos
        params = {"per_page": 100, "sort": "pushed", "affiliation": "owner,collaborator,organization_member"}
        return (await self._get(token, "/user/repos", params)).json()

    async def list_branches(self, token: str, full_name: str) -> list[dict]:
        return (await self._get(token, f"/repos/{full_name}/branches", {"per_page": 100})).json()
