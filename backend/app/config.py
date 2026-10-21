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
    database_path: str = "data/ia_voy.db"
    # Carpeta de los repos clonados. Vacía = fuera del proyecto (ver app.analysis.clone.clones_root):
    # dentro de OneDrive/Dropbox la sincronización bloquea los archivos recién clonados.
    clones_path: str = ""
    # API de IA (Gemini): diagnóstico de un archivo (app.diagnostico)
    gemini_api_key: str = ""
    # gemini-2.5-flash ya no está disponible para claves nuevas
    gemini_model: str = "gemini-3.8-flash"


def with_generated_secrets(settings: Settings) -> Settings:
    """
    Completa SECRET_KEY y TOKEN_ENCRYPTION_KEY si no vienen en el entorno: la primera vez las genera y
    las guarda junto a la base de datos (`data/secrets.json`) para que sobrevivan a los reinicios.
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
