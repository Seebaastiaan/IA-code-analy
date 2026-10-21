"""
Inicio de sesión con GitHub. La cuenta de GitHub es la cuenta de la app: el primer login crea el
usuario y cada login renueva el token de GitHub guardado (cifrado) para listar y clonar sus repos.
La sesión de la app es un token firmado con HMAC (SECRET_KEY) que el frontend envía como Bearer.
"""

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
import time

import httpx
from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.db import get_db
from app.errors import ApiError
from app.github.client import GithubAuthError, GithubError, GithubUser
from app.github.deps import Client, States, Store

TOKEN_TTL_S = 30 * 86_400


class Team(BaseModel):
    name: str
    members: int


class User(BaseModel):
    id: str
    name: str
    initials: str
    email: str
    team: Team
    login: str
    avatar_url: str | None


class AuthorizeResponse(BaseModel):
    url: str
    state: str


class CallbackRequest(BaseModel):
    code: str
    state: str


class LoginResponse(BaseModel):
    token: str
    user: User


# ───────────────────────── Tokens de sesión ─────────────────────────


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str, key: str) -> str:
    return _b64(hmac.new(key.encode(), payload.encode(), hashlib.sha256).digest())


def issue_token(user_id: str, settings: Settings) -> str:
    payload = _b64(json.dumps({"sub": user_id, "exp": int(time.time()) + TOKEN_TTL_S}).encode())
    return f"{payload}.{_sign(payload, settings.secret_key)}"


def current_user_id(authorization: str | None = Header(default=None), settings: Settings = Depends(get_settings)) -> str:
    """Id del usuario de la sesión; 401 si falta el token, está alterado o venció."""
    scheme, _, token = (authorization or "").partition(" ")
    payload, _, signature = token.partition(".")
    if scheme.lower() != "bearer" or not payload or not hmac.compare_digest(signature, _sign(payload, settings.secret_key)):
        raise ApiError(401, "unauthorized", "Inicia sesión para continuar")
    data = json.loads(_unb64(payload))
    if data["exp"] < time.time():
        raise ApiError(401, "session_expired", "Tu sesión expiró")
    return data["sub"]


# ───────────────────────── Usuarios ─────────────────────────


def _initials(name: str) -> str:
    parts = name.replace("-", " ").replace("_", " ").split()
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def user_view(conn: sqlite3.Connection, row: sqlite3.Row) -> User:
    # Import local: app.teams depende de app.analysis, que a su vez usa este módulo
    from app.teams.store import membership

    team_id = membership(conn, row["id"])["team_id"]
    team = conn.execute("SELECT name FROM teams WHERE id = ?", (team_id,)).fetchone()
    count = conn.execute("SELECT COUNT(*) FROM team_members WHERE team_id = ?", (team_id,)).fetchone()[0]
    return User(
        id=row["id"],
        name=row["name"],
        initials=_initials(row["name"]),
        email=row["email"],
        team=Team(name=team["name"], members=count),
        login=row["login"],
        avatar_url=row["avatar_url"],
    )


def upsert_user(conn: sqlite3.Connection, gh: GithubUser) -> sqlite3.Row:
    """Crea el usuario la primera vez que entra y actualiza su perfil en cada login."""
    name = gh.name or gh.login
    conn.execute(
        """INSERT INTO users (id, github_id, login, name, email, avatar_url) VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(github_id) DO UPDATE SET login = excluded.login, name = excluded.name,
           email = excluded.email, avatar_url = excluded.avatar_url""",
        (f"u{secrets.token_hex(6)}", gh.id, gh.login, name, gh.email or "", gh.avatar_url),
    )
    conn.commit()
    return conn.execute("SELECT * FROM users WHERE github_id = ?", (gh.id,)).fetchone()


# ───────────────────────── Rutas ─────────────────────────

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/github/authorize", response_model=AuthorizeResponse)
def github_authorize(client: Client, states: States) -> AuthorizeResponse:
    state = states.issue()
    return AuthorizeResponse(url=client.authorize_url(state), state=state)


@router.post("/github/callback", response_model=LoginResponse)
async def github_callback(
    body: CallbackRequest, client: Client, store: Store, states: States, conn: sqlite3.Connection = Depends(get_db), settings: Settings = Depends(get_settings)
) -> LoginResponse:
    if not states.consume(body.state):
        raise ApiError(400, "invalid_state", "El inicio de sesión expiró o no es válido. Vuelve a intentarlo.")
    try:
        grant = await client.exchange_code(body.code)
        gh = await client.get_user(grant.access_token)
    except GithubError as exc:
        raise ApiError(400, "github_oauth_failed", str(exc)) from exc
    except (GithubAuthError, httpx.HTTPError) as exc:
        raise ApiError(502, "github_unavailable", "No se pudo completar el inicio de sesión con GitHub") from exc
    row = upsert_user(conn, gh)
    store.save(row["id"], gh.login, gh.avatar_url, grant.access_token, grant.scope)
    return LoginResponse(token=issue_token(row["id"], settings), user=user_view(conn, row))


@router.get("/me", response_model=User)
def me(user_id: str = Depends(current_user_id), conn: sqlite3.Connection = Depends(get_db)) -> User:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise ApiError(401, "unauthorized", "Inicia sesión para continuar")
    return user_view(conn, row)


@router.post("/logout", status_code=204)
def logout() -> Response:
    # Los tokens de sesión no tienen estado en el servidor: el frontend los descarta.
    return Response(status_code=204)
