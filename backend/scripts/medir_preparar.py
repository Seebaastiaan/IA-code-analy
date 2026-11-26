"""
Mide «Preparar todo» de punta a punta con Gemini real y el sandbox (docs/PLAN_REGLAS_AUTOMATICO.md, pasos 1 y 2).

    cd backend && uv run python scripts/medir_preparar.py [inventario_demo|reservas_demo] [corridas]

Copia el demo de seed_data tal como se publica (sin arnés ni pruebas: la IA propone el arnés, como en cualquier repo), carga
las reglas de su clave (seed_data/<demo>_clave), corre «Preparar todo» y un análisis, y compara con referencia/ESPERADO.md:
aciertos, falsos positivos (la regla se cumple y sale «no cumple»), falsos negativos (al revés) y si lo que aprobó solo
el programa era correcto. Usa GEMINI_API_KEY y SANDBOX de backend/.env. Escribe ia_voy_preparar/resultado-<demo>.json en
MEDIR_DIR (por omisión, la carpeta temporal del sistema). No toca el repo.
"""

import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

DEMO = sys.argv[1] if len(sys.argv) > 1 else "inventario_demo"
RUNS = int(sys.argv[2]) if len(sys.argv) > 2 else 1
S = Path(os.environ.get("MEDIR_DIR") or tempfile.gettempdir()) / "ia_voy_preparar"
S.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, ".")

from fastapi.testclient import TestClient

from app.analysis import clone as clone_mod
from app.analysis import router as analysis_router
from app.analysis.clone import CloneResult
from app.analysis.jobs import JobManager
from app.config import Settings, get_settings
from app.github import deps
from app.main import create_app
from tests.conftest import FakeGithub, login
from tests.test_analysis import URL, wait_done

SEED = Path("seed_data").resolve() / DEMO
KEY = Path("seed_data").resolve() / f"{DEMO}_clave"
EXPECTED = {
    m.group(1): ("no_cumple" if "no cumple" in line else "cumple")
    for line in (KEY / "referencia/ESPERADO.md").read_text(encoding="utf-8").splitlines()
    if (m := re.match(r"\| (RN-\d{3}) \|", line))
}
VIOLATED = ("no_cumple", "no_implementada")


class DemoCloner:
    """En lugar de git: copia el demo tal como se publica."""

    def clone(self, settings, repo_id, url, branch, token, attempt) -> CloneResult:
        tmp = clone_mod.clones_root(settings) / f"{repo_id}.tmp-{attempt}"
        shutil.copytree(SEED, tmp, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.db"))
        (tmp / ".git").mkdir()
        return CloneResult(py_files=len(clone_mod.python_files(tmp)), seconds=0.1, commit="demo000")

    promote = staticmethod(clone_mod.promote)


def outcome(expected: str, got: str | None) -> str:
    if got is None or got not in ("cumple", *VIOLATED):
        return "sin_resultado"
    if expected == "cumple":
        return "acierto" if got == "cumple" else "falso_positivo"
    return "acierto" if got in VIOLATED else "falso_negativo"


def one_run(n: int) -> dict:
    work = S / f"{DEMO}-{n}"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    os.environ.update(DATABASE_PATH=str(work / "ia.db"), CLONES_PATH=str(work / "clones"))
    settings = Settings()
    if not settings.gemini_api_key or settings.sandbox == "off":
        raise SystemExit("Hace falta GEMINI_API_KEY y SANDBOX (wsl o docker) en backend/.env")
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[deps.get_client] = lambda: FakeGithub(settings)
    jobs = JobManager(DemoCloner())
    app.dependency_overrides[analysis_router.get_jobs] = lambda: jobs
    t0 = time.time()
    with TestClient(app) as client:
        login(client)
        rid = wait_done(client, client.post("/api/analyze", json={"url": URL}).json()["job_id"], timeout=1800)["repo_id"]
        res = client.put(f"/api/projects/{rid}/reglas", json={"content": (KEY / "referencia/reglas_negocio.toml").read_text(encoding="utf-8")})
        assert res.status_code == 200, res.text
        assert client.post(f"/api/projects/{rid}/reglas/preparar").status_code == 200
        last = ""
        while True:
            view = client.get(f"/api/projects/{rid}/reglas/preparar").json()
            line = " | ".join(f"{s['id']}:{s['status']}" for s in view["steps"])
            if line != last:
                print(f"[{n}] {int(time.time() - t0)}s {line}", flush=True)
                last = line
            if not view["running"]:
                break
            time.sleep(10)
        prepared = time.time() - t0
        tests = client.get(f"/api/projects/{rid}/reglas/pruebas").json()
        # El análisis con las pruebas aprobadas: es lo que vería el equipo en el reporte
        wait_done(client, client.post(f"/api/repos/{rid}/analyze").json()["job_id"], timeout=1800)
        report = client.get("/api/report/latest/reglas", params={"repo": rid}).json()

    reported = {r["id"]: r["status"] for r in report["rules"]}
    rows = []
    for r in tests["rules"]:
        t = r["test"] or {}
        run = (t.get("run") or {}).get("verdict")
        rows.append({
            "id": r["id"], "esperado": EXPECTED.get(r["id"]), "prueba": run, "resultado_prueba": outcome(EXPECTED.get(r["id"], "cumple"), run),
            "fuerza": (t.get("strength") or {}).get("status"), "segunda_opinion": r["crosscheck"]["status"], "aprobada": t.get("approved", False),
            "reporte": reported.get(r["id"]), "resultado_reporte": outcome(EXPECTED.get(r["id"], "cumple"), reported.get(r["id"])),
        })
    count = lambda key, value: sum(1 for x in rows if x[key] == value)
    approved = [x for x in rows if x["aprobada"]]
    return {
        "corrida": n, "minutos_preparar": round(prepared / 60, 1), "pasos": {s["id"]: s["note"] for s in view["steps"]}, "resumen_preparar": view["summary"],
        "pruebas": {k: count("resultado_prueba", k) for k in ("acierto", "falso_positivo", "falso_negativo", "sin_resultado")},
        "reporte": {k: count("resultado_reporte", k) for k in ("acierto", "falso_positivo", "falso_negativo", "sin_resultado")},
        "aprobadas_por_el_programa": len(approved), "aprobadas_incorrectas": sum(1 for x in approved if x["resultado_prueba"] != "acierto"),
        "discrepan": count("segunda_opinion", "discrepa"), "reglas": rows,
    }


results = []
for i in range(1, RUNS + 1):
    results.append(one_run(i))
    r = results[-1]
    print(json.dumps({k: v for k, v in r.items() if k != "reglas"}, ensure_ascii=False, indent=2), flush=True)
out = S / f"resultado-{DEMO}.json"
out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Resultado en {out}")
