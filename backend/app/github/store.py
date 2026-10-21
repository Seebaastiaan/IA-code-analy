import sqlite3
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken


@dataclass
class GithubAccount:
    user_id: str
    login: str
    avatar_url: str | None
    token: str


class GithubAccountStore:
    """Cuenta de GitHub vinculada a cada usuario. El token se guarda cifrado (Fernet)."""

    def __init__(self, conn: sqlite3.Connection, fernet: Fernet):
        self.conn = conn
        self.fernet = fernet

    def get(self, user_id: str) -> GithubAccount | None:
        row = self.conn.execute("SELECT * FROM github_accounts WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            return None
        try:
            token = self.fernet.decrypt(row["token_enc"].encode()).decode()
        except InvalidToken:
            # Cambió TOKEN_ENCRYPTION_KEY: el token guardado ya no sirve y hay que volver a conectar
            self.delete(user_id)
            return None
        return GithubAccount(user_id=user_id, login=row["login"], avatar_url=row["avatar_url"], token=token)

    def save(self, user_id: str, login: str, avatar_url: str | None, token: str, scopes: str) -> None:
        token_enc = self.fernet.encrypt(token.encode()).decode()
        self.conn.execute(
            """INSERT INTO github_accounts (user_id, login, avatar_url, token_enc, scopes) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET login = excluded.login, avatar_url = excluded.avatar_url,
               token_enc = excluded.token_enc, scopes = excluded.scopes, created_at = datetime('now')""",
            (user_id, login, avatar_url, token_enc, scopes),
        )
        self.conn.commit()

    def delete(self, user_id: str) -> None:
        self.conn.execute("DELETE FROM github_accounts WHERE user_id = ?", (user_id,))
        self.conn.commit()
