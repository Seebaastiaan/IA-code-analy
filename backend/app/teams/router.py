"""
Equipo del usuario (docs/FRONTEND_SPEC.md: "repositorios conectados al equipo", "solo miembros del equipo").

- GET /api/team, PATCH /api/team (nombre, solo el dueño)
- POST /api/team/invites (dueño): enlace /join/{code} válido 7 días, reutilizable por varias personas
- GET /api/team/invites/{code}: vista previa antes de unirse (equipo, miembros y repos que se descartarían)
- POST /api/team/join {code}: cambia de equipo
- DELETE /api/team/members/{user_id}: el dueño quita a alguien, o un miembro se sale ("me")
- POST /api/team/members/{user_id}/owner: el dueño cede el equipo
"""

import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from app.auth import current_user_id
from app.config import Settings, get_settings
from app.db import get_db
from app.errors import ApiError
from app.teams import store

router = APIRouter(prefix="/api/team", tags=["equipo"])

INVITE_DAYS = 7

UserId = Annotated[str, Depends(current_user_id)]
Db = Annotated[sqlite3.Connection, Depends(get_db)]
Config = Annotated[Settings, Depends(get_settings)]


class Member(BaseModel):
    id: str
    name: str
    login: str
    avatar_url: str | None
    role: Literal["owner", "member"]
    joined_at: str


class TeamResponse(BaseModel):
    id: str
    name: str
    role: Literal["owner", "member"]
    members: list[Member]
    repos: int


class RenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class InviteResponse(BaseModel):
    code: str
    url: str
    expires_at: str


class InvitePreview(BaseModel):
    team_name: str
    members: int
    invited_by: str
    expires_at: str
    already_member: bool
    # Repos propios que se descartarían al unirse porque el equipo ya los tiene
    conflicts: list[str]


class JoinRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)


def _team(conn: sqlite3.Connection, user_id: str) -> TeamResponse:
    me = store.membership(conn, user_id)
    team = conn.execute("SELECT * FROM teams WHERE id = ?", (me["team_id"],)).fetchone()
    repos = conn.execute("SELECT COUNT(*) FROM repos WHERE team_id = ?", (team["id"],)).fetchone()[0]
    return TeamResponse(id=team["id"], name=team["name"], role=me["role"], members=[Member(**dict(m)) for m in store.members(conn, team["id"])], repos=repos)


def _require_owner(conn: sqlite3.Connection, user_id: str) -> sqlite3.Row:
    me = store.membership(conn, user_id)
    if me["role"] != "owner":
        raise ApiError(403, "not_owner", "Solo quien administra el equipo puede hacer esto")
    return me


def _open_invite(conn: sqlite3.Connection, code: str) -> sqlite3.Row:
    invite = conn.execute("SELECT * FROM team_invites WHERE code = ?", (code,)).fetchone()
    if invite is None:
        raise ApiError(404, "not_found", "Esta invitación no existe")
    if datetime.fromisoformat(invite["expires_at"]) < datetime.now(UTC):
        raise ApiError(410, "expired", "Esta invitación expiró. Pide una nueva.")
    return invite


@router.get("", response_model=TeamResponse)
def get_team(user_id: UserId, conn: Db) -> TeamResponse:
    return _team(conn, user_id)


@router.patch("", response_model=TeamResponse)
def rename_team(body: RenameRequest, user_id: UserId, conn: Db) -> TeamResponse:
    me = _require_owner(conn, user_id)
    conn.execute("UPDATE teams SET name = ? WHERE id = ?", (body.name.strip(), me["team_id"]))
    conn.commit()
    return _team(conn, user_id)


@router.post("/invites", response_model=InviteResponse)
def create_invite(user_id: UserId, conn: Db, settings: Config, origin: str | None = Header(default=None)) -> InviteResponse:
    me = _require_owner(conn, user_id)
    code = secrets.token_urlsafe(12)
    expires_at = (datetime.now(UTC) + timedelta(days=INVITE_DAYS)).isoformat(timespec="seconds").replace("+00:00", "Z")
    conn.execute(
        "INSERT INTO team_invites (code, team_id, created_by, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
        (code, me["team_id"], user_id, expires_at, store.now_iso()),
    )
    conn.commit()
    base = (origin if origin and origin.startswith(("http://", "https://")) else settings.frontend_url).rstrip("/")
    return InviteResponse(code=code, url=f"{base}/join/{code}", expires_at=expires_at)


@router.get("/invites/{code}", response_model=InvitePreview)
def preview_invite(code: str, user_id: UserId, conn: Db) -> InvitePreview:
    invite = _open_invite(conn, code)
    team = conn.execute("SELECT name FROM teams WHERE id = ?", (invite["team_id"],)).fetchone()
    if team is None:
        raise ApiError(404, "not_found", "Este equipo ya no existe")
    author = conn.execute("SELECT name FROM users WHERE id = ?", (invite["created_by"],)).fetchone()
    count = conn.execute("SELECT COUNT(*) FROM team_members WHERE team_id = ?", (invite["team_id"],)).fetchone()[0]
    mine = store.team_id_of(conn, user_id)
    return InvitePreview(
        team_name=team["name"], members=count, invited_by=author["name"] if author else "alguien del equipo", expires_at=invite["expires_at"],
        already_member=mine == invite["team_id"], conflicts=[] if mine == invite["team_id"] else store.conflicts(conn, user_id, invite["team_id"]),
    )


def _check_can_leave(conn: sqlite3.Connection, user_id: str) -> None:
    me = store.membership(conn, user_id)
    others = conn.execute("SELECT COUNT(*) FROM team_members WHERE team_id = ? AND user_id != ?", (me["team_id"], user_id)).fetchone()[0]
    if me["role"] == "owner" and others:
        raise ApiError(409, "owner_must_transfer", "Administras un equipo con más miembros: cédelo a alguien antes de salir")


@router.post("/join", response_model=TeamResponse)
def join(body: JoinRequest, user_id: UserId, conn: Db, settings: Config) -> TeamResponse:
    invite = _open_invite(conn, body.code)
    if store.team_id_of(conn, user_id) == invite["team_id"]:
        return _team(conn, user_id)
    _check_can_leave(conn, user_id)
    store.move_user(settings, conn, user_id, invite["team_id"])
    conn.commit()
    return _team(conn, user_id)


@router.delete("/members/{member_id}", response_model=TeamResponse)
def remove_member(member_id: str, user_id: UserId, conn: Db, settings: Config) -> TeamResponse:
    """`me` = salir del equipo (a uno propio y vacío). Otro id: el dueño lo quita del equipo."""
    me = store.membership(conn, user_id)
    if member_id in ("me", user_id):
        _check_can_leave(conn, user_id)
        if conn.execute("SELECT COUNT(*) FROM team_members WHERE team_id = ?", (me["team_id"],)).fetchone()[0] == 1:
            raise ApiError(409, "already_alone", "Eres el único miembro de este equipo")
        store.move_user(settings, conn, user_id, None)
    else:
        _require_owner(conn, user_id)
        target = conn.execute("SELECT team_id FROM team_members WHERE user_id = ?", (member_id,)).fetchone()
        if target is None or target["team_id"] != me["team_id"]:
            raise ApiError(404, "not_found", "Esa persona no es del equipo")
        store.move_user(settings, conn, member_id, None)
    conn.commit()
    return _team(conn, user_id)


@router.post("/members/{member_id}/owner", response_model=TeamResponse)
def transfer_ownership(member_id: str, user_id: UserId, conn: Db) -> TeamResponse:
    me = _require_owner(conn, user_id)
    target = conn.execute("SELECT team_id FROM team_members WHERE user_id = ?", (member_id,)).fetchone()
    if target is None or target["team_id"] != me["team_id"] or member_id == user_id:
        raise ApiError(404, "not_found", "Esa persona no es del equipo")
    conn.execute("UPDATE team_members SET role = 'member' WHERE user_id = ?", (user_id,))
    conn.execute("UPDATE team_members SET role = 'owner' WHERE user_id = ?", (member_id,))
    conn.commit()
    return _team(conn, user_id)
