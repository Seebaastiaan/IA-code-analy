from cryptography.fernet import Fernet

from app.config import Settings, with_generated_secrets


def test_genera_y_reutiliza_claves(tmp_path):
    base = Settings(_env_file=None, secret_key="", token_encryption_key="", database_path=str(tmp_path / "data" / "app.db"))

    first = with_generated_secrets(base)
    assert first.secret_key
    Fernet(first.token_encryption_key)  # clave Fernet válida
    assert (tmp_path / "data" / "secrets.json").exists()

    # Tras reiniciar se usan las mismas claves (las sesiones y tokens guardados siguen sirviendo)
    second = with_generated_secrets(base)
    assert (second.secret_key, second.token_encryption_key) == (first.secret_key, first.token_encryption_key)


def test_las_del_entorno_tienen_prioridad(tmp_path):
    key = Fernet.generate_key().decode()
    s = with_generated_secrets(Settings(_env_file=None, secret_key="propia", token_encryption_key=key, database_path=str(tmp_path / "app.db")))
    assert (s.secret_key, s.token_encryption_key) == ("propia", key)
    assert not (tmp_path / "secrets.json").exists()
