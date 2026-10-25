from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Path, Query

from app.auth import current_user_id
from app.errors import ApiError
from app.github.client import GithubAuthError, GithubError
from app.github.deps import Client, Store
from app.github.schemas import GithubBranch, GithubRepo, GithubStatus
from app.github.store import GithubAccount, GithubAccountStore

router = APIRouter(prefix="/api/github", tags=["github"])

# Nombres válidos de owner/repo en GitHub; evita que el path salga de /repos/{owner}/{repo}
NAME = r"^[A-Za-z0-9._-]{1,100}$"

UserId = Annotated[str, Depends(current_user_id)]


def not_connected(message: str = "Vuelve a iniciar sesión con GitHub para ver tus repositorios") -> ApiError:
    # 409 (no 401): el frontend trata cualquier 401 como sesión de la app vencida y la cierra
    return ApiError(409, "github_not_connected", message)


def require_account(store: Store, user_id: UserId) -> GithubAccount:
    account = store.get(user_id)
    if account is None:
        raise not_connected()
    return account


Account = Annotated[GithubAccount, Depends(require_account)]


def github_failure(store: GithubAccountStore, user_id: str, exc: Exception) -> ApiError:
    """Traduce un fallo de GitHub; si revocaron el token, lo descarta."""
    if isinstance(exc, GithubAuthError):
        store.delete(user_id)
        return not_connected("GitHub revocó el acceso. Vuelve a iniciar sesión con GitHub.")
    if isinstance(exc, GithubError) and exc.status == 404:
        return ApiError(404, "not_found", "Repositorio no encontrado o sin acceso")
    if isinstance(exc, GithubError) and exc.status in (403, 429):
        return ApiError(503, "github_rate_limited", "GitHub limitó las solicitudes. Intenta en unos minutos.")
    if isinstance(exc, httpx.HTTPError):
        return ApiError(502, "github_unavailable", "No se pudo contactar a GitHub")
    return ApiError(502, "github_error", str(exc))


@router.get("/status", response_model=GithubStatus)
def status(store: Store, user_id: UserId) -> GithubStatus:
    account = store.get(user_id)
    if account is None:
        return GithubStatus(connected=False)
    return GithubStatus(connected=True, login=account.login, avatar_url=account.avatar_url)


@router.get("/repos", response_model=list[GithubRepo])
async def repos(client: Client, store: Store, account: Account, q: str | None = Query(default=None, max_length=100)) -> list[GithubRepo]:
    try:
        raw = await client.list_repos(account.token)
    except (GithubAuthError, GithubError, httpx.HTTPError) as exc:
        raise github_failure(store, account.user_id, exc) from exc
    term = (q or "").strip().lower()
    return [
        GithubRepo(full_name=r["full_name"], html_url=r["html_url"], default_branch=r["default_branch"], private=r["private"], description=r.get("description"), pushed_at=r.get("pushed_at") or r["updated_at"])
        for r in raw
        if term in r["full_name"].lower()
    ]


@router.get("/repos/{owner}/{repo}/branches", response_model=list[GithubBranch])
async def branches(client: Client, store: Store, account: Account, owner: str = Path(pattern=NAME), repo: str = Path(pattern=NAME)) -> list[GithubBranch]:
    if set(owner) == {"."} or set(repo) == {"."}:
        raise ApiError(404, "not_found", "Repositorio no encontrado o sin acceso")
    try:
        raw = await client.list_branches(account.token, f"{owner}/{repo}")
    except (GithubAuthError, GithubError, httpx.HTTPError) as exc:
        raise github_failure(store, account.user_id, exc) from exc
    return [GithubBranch(name=b["name"]) for b in raw]
