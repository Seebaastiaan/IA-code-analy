"""
Datos de demostración para tablero, reporte y editor sin tener que analizar un repo de GitHub.

    python -m app.seed --login tu-usuario-de-github

Copia `seed_data/demo_repo` como clon de un repo de ese usuario (ya debe haber entrado con GitHub) y
corre Ruff, Bandit y Radon de verdad sobre ella. La cobertura y las pruebas (que requieren ejecutar el código en el
sandbox) son simuladas. Crea 4 análisis semanales para que la tendencia tenga historia. Es idempotente:
volver a correrlo reemplaza los reportes del repo de demostración.
"""

import argparse
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.analyses.analyzers import complexity, static_findings_dir
from app.analyses.models import CoverageInput, FindingInput, ReportInput
from app.analyses.store import AnalysisStore
from app.analyses.workspace import Workspace
from app.analysis.clone import remove_tree
from app.config import Settings, get_settings
from app.db import connect

DEMO_SOURCE = Path(__file__).resolve().parent.parent / "seed_data" / "demo_repo"
DEMO_NAME = "equipo/api-pagos"
DEMO_URL = "https://github.com/equipo/api-pagos"
COVERAGE = {"auth.py": 82, "api.py": 45, "utils.py": 64, "pagos/procesador.py": 91, "pagos/__init__.py": 100}
# Semanas atrás, cobertura total, pruebas que fallan y cuántos hallazgos de más tenía (para la tendencia)
HISTORY = [(3, 61.0, 3, 6), (2, 66.0, 2, 4), (1, 70.0, 1, 2), (0, 74.0, 1, 0)]


def test_findings(coverage: dict[str, float], failed: int, min_cov: float) -> list[FindingInput]:
    found = [
        FindingInput(
            sev="media" if pct < min_cov - 10 else "baja", cat="test", tool="coverage", rule="COV", file=file, line=1,
            msg=f"Cobertura de {pct:.0f} % (mínimo {min_cov:.0f} %)", why="Las líneas sin probar pueden romperse sin que ninguna prueba lo detecte.",
            rec="Agrega pruebas para las ramas sin cubrir de este archivo.", code="",
        )
        for file, pct in coverage.items()
        if pct < min_cov
    ]
    if failed:
        found.append(FindingInput(
            sev="alta", cat="test", tool="pytest", rule="FAIL", file="tests/test_procesador.py", line=9,
            msg="test_cobra_pago_valido falló: KeyError 'ok'", why="Una prueba que falla indica una regresión o una prueba desactualizada.",
            rec="Ejecuta la prueba localmente con `pytest -x` y corrige el código o la prueba.",
        ))
    return found


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
    files = ws.list_files([])
    py = [f for f in files if f.endswith(".py")]
    static = static_findings_dir(ws.root, files)
    cc = complexity(ws.root, py)
    avg_cc = round(sum(c.cc for c in cc) / len(cc), 1) if cc else 0.0
    min_cov = store.config(repo_id).thresholds["cov"]

    now = datetime.now(UTC).replace(microsecond=0)
    for weeks_ago, cov_total, failed, extra in HISTORY:
        coverage = {f: max(0, pct - (74 - cov_total)) for f, pct in COVERAGE.items()}
        # Los análisis anteriores tenían además algunos hallazgos que después se corrigieron
        findings = static + static[:extra] + test_findings(coverage, failed, min_cov)
        store.save_report(repo_id, ReportInput(
            branch="main", commit=f"{0xA3F9C1E - weeks_ago * 4099:07x}", duration_s=150 + weeks_ago * 7,
            coverage_total=cov_total, tests_failed=failed, avg_complexity=avg_cc,
            findings=findings,
            coverage=[CoverageInput(file=f, percent=p) for f, p in sorted(coverage.items(), key=lambda x: x[1])],
            complexity=cc,
            created_at=(now - timedelta(weeks=weeks_ago, hours=2)).isoformat().replace("+00:00", "Z"),
        ), ws)
    store.set_repo_status(repo_id, "listo", files=len(py))
    print(f"Repo de demostración listo: {DEMO_NAME} (id {repo_id}, usuario {user['login']})")
    print(f"  {len(static)} hallazgos de Ruff/Bandit, {len(cc)} funciones medidas, {len(HISTORY)} análisis")
    print(f"  Copia de trabajo: {ws.root}")
    conn.close()
    return repo_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga un repo de demostración para un usuario")
    parser.add_argument("--login", required=True, help="Usuario de GitHub con el que ya entraste a la app")
    seed(parser.parse_args().login)


if __name__ == "__main__":
    main()
