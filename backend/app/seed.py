"""
Datos de demostración para la pantalla Repositorios sin tener que clonar un repo de GitHub.

    python -m app.seed --login tu-usuario-de-github

Copia `seed_data/demo_repo` (el golden repo del equipo de QA) como clon de un repo de ese usuario (ya debe
haber entrado con GitHub) y guarda 3 análisis semanales en su historia. Es idempotente: volver a correrlo
reemplaza los análisis del repo de demostración.
"""

import argparse
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.analyses.store import AnalysisStore
from app.analyses.workspace import Workspace
from app.analysis import languages
from app.analysis.clone import remove_tree
from app.config import Settings, get_settings
from app.db import connect

DEMO_SOURCE = Path(__file__).resolve().parent.parent / "seed_data" / "demo_repo"
DEMO_NAME = "equipo/api-pagos"
DEMO_URL = "https://github.com/equipo/api-pagos"
# Semanas atrás y duración (s) de cada análisis guardado
HISTORY = [(2, 14), (1, 12), (0, 11)]


def seed(login: str, settings: Settings | None = None) -> str:
    """Carga el repo de demostración para el usuario y devuelve su id."""
    settings = settings or get_settings()
    conn = connect(settings.database_path)
    user = conn.execute("SELECT id, login FROM users WHERE login = ? COLLATE NOCASE", (login.strip(),)).fetchone()
    if user is None:
        raise SystemExit(f"No existe el usuario de GitHub «{login}». Entra primero a la app con GitHub.")

    store = AnalysisStore(conn)
    repo_id = store.upsert_repo(user["id"], DEMO_NAME, DEMO_URL, "main")
    conn.execute("DELETE FROM reports WHERE repo_id = ?", (repo_id,))
    conn.commit()

    ws = Workspace(settings, repo_id)
    remove_tree(ws.root)
    shutil.copytree(DEMO_SOURCE, ws.root)
    found = languages.detect(ws.root)
    langs = [{"name": lang.name, "files": lang.files} for lang in found]

    now = datetime.now(UTC).replace(microsecond=0)
    for weeks_ago, seconds in HISTORY:
        store.save_report(
            repo_id, branch="main", commit=f"{0xA3F9C1E - weeks_ago * 4099:07x}", duration_s=seconds, languages=langs,
            created_at=(now - timedelta(weeks=weeks_ago, hours=2)).isoformat().replace("+00:00", "Z"),
        )
    store.set_repo_status(repo_id, "listo", files=languages.python_files(found))
    print(f"Repo de demostración listo: {DEMO_NAME} (id {repo_id}, usuario {user['login']})")
    print(f"  {languages.summary(found)} · {len(HISTORY)} análisis guardados")
    print(f"  Copia de trabajo: {ws.root}")
    conn.close()
    return repo_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga un repo de demostración para un usuario")
    parser.add_argument("--login", required=True, help="Usuario de GitHub con el que ya entraste a la app")
    seed(parser.parse_args().login)


if __name__ == "__main__":
    main()
