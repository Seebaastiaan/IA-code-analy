"""
Equipos: cada usuario pertenece a exactamente uno (tabla team_members). Los repos, sus reportes, la
configuración y el asistente son del equipo: cualquier miembro los ve y los analiza.
El primer login crea un equipo propio ("Equipo de Ana"); para trabajar juntos, el dueño comparte un
enlace de invitación (app.teams.router).
"""

import secrets
import shutil
import sqlite3
from datetime import UTC, datetime

from app.analysis.clone import clone_dir
from app.config import Settings


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


def members(conn: sqlite3.Connection, team_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT u.id, u.name, u.login, u.avatar_url, m.role, m.joined_at FROM team_members m JOIN users u ON u.id = m.user_id
           WHERE m.team_id = ? ORDER BY m.role = 'owner' DESC, m.joined_at""",
        (team_id,),
    ).fetchall()


def delete_repo(settings: Settings, conn: sqlite3.Connection, repo_id: str) -> None:
    """Borra un repo con sus reportes, hallazgos, índice y clon (la cascada de SQLite hace el resto)."""
    conn.execute("DELETE FROM repos WHERE id = ?", (repo_id,))
    shutil.rmtree(clone_dir(settings, repo_id), ignore_errors=True)


def move_user(settings: Settings, conn: sqlite3.Connection, user_id: str, new_team_id: str | None) -> None:
    """
    Saca al usuario de su equipo actual. Si era el único miembro, sus repos pasan al equipo nuevo (los que
    ya existen allí con el mismo nombre se descartan: el equipo ya tiene los suyos) y el equipo viejo se
    borra. Si había más miembros, los repos se quedan con ellos. `new_team_id` None = equipo propio nuevo.
    """
    old = membership(conn, user_id)["team_id"]
    alone = conn.execute("SELECT COUNT(*) FROM team_members WHERE team_id = ?", (old,)).fetchone()[0] == 1
    if new_team_id is None:
        new_team_id = create_team(conn, user_id, personal_team_name(conn, user_id))
    else:
        conn.execute("UPDATE team_members SET team_id = ?, role = 'member', joined_at = ? WHERE user_id = ?", (new_team_id, now_iso(), user_id))
    if alone:
        taken = {r["name"].lower() for r in conn.execute("SELECT name FROM repos WHERE team_id = ?", (new_team_id,))}
        for repo in conn.execute("SELECT id, name FROM repos WHERE team_id = ?", (old,)).fetchall():
            if repo["name"].lower() in taken:
                delete_repo(settings, conn, repo["id"])
            else:
                conn.execute("UPDATE repos SET team_id = ? WHERE id = ?", (new_team_id, repo["id"]))
        conn.execute("UPDATE jobs SET team_id = ? WHERE team_id = ?", (new_team_id, old))
        conn.execute("DELETE FROM teams WHERE id = ?", (old,))


def conflicts(conn: sqlite3.Connection, user_id: str, team_id: str) -> list[str]:
    """Repos que el usuario perdería al unirse a `team_id` (solo si es el único miembro de su equipo actual)."""
    old = membership(conn, user_id)["team_id"]
    if conn.execute("SELECT COUNT(*) FROM team_members WHERE team_id = ?", (old,)).fetchone()[0] > 1:
        return []
    rows = conn.execute(
        "SELECT a.name FROM repos a JOIN repos b ON lower(a.name) = lower(b.name) WHERE a.team_id = ? AND b.team_id = ? ORDER BY a.name",
        (old, team_id),
    ).fetchall()
    return [r["name"] for r in rows]
