"""Dependencias compartidas por el login (app.auth) y las rutas /api/github."""

import sqlite3
from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from cryptography.fernet import Fernet
from fastapi import Depends

from app.config import Settings, get_settings
from app.db import get_db
from app.errors import ApiError
from app.github.client import GithubClient
from app.github.states import OAuthStates
from app.github.store import GithubAccountStore


def get_states(conn: sqlite3.Connection = Depends(get_db)) -> OAuthStates:
    return OAuthStates(conn)


async def get_client(settings: Settings = Depends(get_settings)) -> AsyncIterator[GithubClient]:
    if not (settings.github_client_id and settings.github_client_secret):
        raise ApiError(503, "github_not_configured", "Falta configurar GITHUB_CLIENT_ID y GITHUB_CLIENT_SECRET en el backend")
    async with httpx.AsyncClient(timeout=15) as http:
        yield GithubClient(settings, http)


def get_store(conn: sqlite3.Connection = Depends(get_db), settings: Settings = Depends(get_settings)) -> GithubAccountStore:
    return GithubAccountStore(conn, Fernet(settings.token_encryption_key))


Client = Annotated[GithubClient, Depends(get_client)]
Store = Annotated[GithubAccountStore, Depends(get_store)]
States = Annotated[OAuthStates, Depends(get_states)]
