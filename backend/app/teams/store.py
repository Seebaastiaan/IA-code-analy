"""
Equipos: cada usuario pertenece a exactamente uno (tabla team_members). Los repos y sus reportes son del
equipo. El primer login crea un equipo propio ("Equipo de Ana").
"""

import secrets
import sqlite3
from datetime import UTC, datetime


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def create_team(conn: sqlite3.Connection, user_id: str, name: str) -> str:
    """Equipo nuevo con el usuario como dueño (sin confirmar la transacción)."""
    team_id = f"t{secrets.token_hex(6)}"
    conn.execute("INSERT INTO teams (id, name, created_at) VALUES (?, ?, ?)", (team_id, name[:80], now_iso()))
    conn.execute(
        "INSERT INTO team_members (user_id, team_id, role, joined_at) VALUES (?, ?, 'owner', ?) "
        "ON CONFLICT(user_id) DO UPDATE SET team_id = excluded.team_id, role = 'owner', joined_at = excluded.joined_at",
        (user_id, team_id, now_iso()),
    )
    return team_id


def personal_team_name(conn: sqlite3.Connection, user_id: str) -> str:
    row = conn.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
    return f"Equipo de {row['name'] if row else 'IA voy'}"


def membership(conn: sqlite3.Connection, user_id: str) -> sqlite3.Row:
    """(team_id, role) del usuario; si aún no tiene equipo (usuario recién creado) le crea el suyo."""
    row = conn.execute("SELECT team_id, role FROM team_members WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        create_team(conn, user_id, personal_team_name(conn, user_id))
        conn.commit()
        row = conn.execute("SELECT team_id, role FROM team_members WHERE user_id = ?", (user_id,)).fetchone()
    return row


def team_id_of(conn: sqlite3.Connection, user_id: str) -> str:
    return membership(conn, user_id)["team_id"]
