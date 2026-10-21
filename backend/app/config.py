import json
import secrets
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración desde variables de entorno o `backend/.env` (ver `.env.example`)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    frontend_url: str = "http://localhost:5173"
    secret_key: str = ""
    token_encryption_key: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    database_path: str = "data/ia_voy.db"
    # Carpeta de los repos clonados. Vacía = fuera del proyecto (ver app.analysis.clone.clones_root):
    # dentro de OneDrive/Dropbox la sincronización bloquea los archivos recién clonados.
    clones_path: str = ""
    # Pausa visual entre los pasos del análisis (11 pasos) para seguirlos en la terminal en vivo
    job_step_seconds: float = 0.9
    # API de IA (Gemini). El análisis no la usa: el motor es determinista (docs/adr/ADR-001)
    gemini_api_key: str = ""
    # gemini-2.5-flash ya no está disponible para claves nuevas
    gemini_model: str = "gemini-3.8-flash"

    @property
    def github_redirect_uri(self) -> str:
        return f"{self.frontend_url.rstrip('/')}/github/callback"


def with_generated_secrets(settings: Settings) -> Settings:
    """
    Completa SECRET_KEY y TOKEN_ENCRYPTION_KEY si no vienen en el entorno: la primera vez las genera y
    las guarda junto a la base de datos (`data/secrets.json`) para que sobrevivan a los reinicios.
    Si ese archivo se pierde, las sesiones vencen y hay que volver a conectar GitHub.
    """
    if settings.secret_key and settings.token_encryption_key:
        return settings
    path = Path(settings.database_path).parent / "secrets.json"
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        stored = {}
    generated = {
        "secret_key": stored.get("secret_key") or secrets.token_urlsafe(48),
        "token_encryption_key": stored.get("token_encryption_key") or Fernet.generate_key().decode(),
    }
    if generated != stored:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(generated, indent=2), encoding="utf-8")
    return settings.model_copy(
        update={
            "secret_key": settings.secret_key or generated["secret_key"],
            "token_encryption_key": settings.token_encryption_key or generated["token_encryption_key"],
        }
    )


@lru_cache
def get_settings() -> Settings:
    return with_generated_secrets(Settings())
