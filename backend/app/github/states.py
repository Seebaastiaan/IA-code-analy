import secrets
import sqlite3
import time

STATE_TTL_S = 10 * 60


class OAuthStates:
    """
    `state` de OAuth emitidos por el backend: se usan una sola vez y vencen en 10 minutos.
    El frontend además comprueba que el `state` que regresa sea el que él inició (anti login-CSRF).
    Viven en SQLite (tabla `oauth_states`): sobreviven a un reinicio y los comparten varios workers.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def issue(self) -> str:
        state = secrets.token_urlsafe(24)
        now = time.time()
        with self.conn:
            self.conn.execute("DELETE FROM oauth_states WHERE expires_at <= ?", (now,))
            self.conn.execute("INSERT INTO oauth_states (state, expires_at) VALUES (?, ?)", (state, now + STATE_TTL_S))
        return state

    def consume(self, state: str) -> bool:
        # DELETE ... RETURNING: un solo uso aunque lleguen dos callbacks a la vez
        with self.conn:
            row = self.conn.execute("DELETE FROM oauth_states WHERE state = ? RETURNING expires_at", (state,)).fetchone()
        return row is not None and row["expires_at"] > time.time()
