"""
Mide el mapa, el arnés (Gemini real) y la prueba de humo (Docker) en un repo público (§7.6). Solo se clona con la URL en una
carpeta temporal; su código no se copia al repo.

    cd backend && uv run python scripts/medir_repo_publico.py <id> <url> <rama>

Para repos con dependencias que se compilan: SANDBOX_DOCKER_IMAGE=ghcr.io/astral-sh/uv:python3.12-bookworm (1.5 GB).
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRATCH = Path(os.environ.get("MEDIR_DIR") or tempfile.gettempdir()) / "ia_voy_medir"
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ["CLONES_PATH"] = str(SCRATCH / "clones")
os.environ["SANDBOX"] = "docker"
os.environ.setdefault("SANDBOX_DOCKER_IMAGE", "ghcr.io/astral-sh/uv:python3.12-bookworm")
os.environ["DATABASE_PATH"] = str(SCRATCH / "ia.db")
sys.path.insert(0, ".")

from app.analyses import mapa
from app.analyses.workspace import Workspace
from app.analysis import sandbox
from app.assistant.llm import LLM
from app.config import Settings
from app.projects import arnes as router
from app.projects import reglas_arnes as ar

rid, url, branch = sys.argv[1:4]
settings = Settings()
dest = SCRATCH / "clones" / rid
if not dest.exists():
    subprocess.run(["git", "clone", "--depth", "1", "--branch", branch, url, str(dest)], check=True, capture_output=True)
commit = subprocess.run(["git", "-C", str(dest), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
ws = Workspace(settings, rid)
t0 = time.time()
mp = mapa.build(ws.root, ws.list_files([]))
out = {"repo": url, "commit": commit, "framework": mp.framework, "endpoints": len(mp.endpoints), "models": len(mp.models), "roles": list(mp.roles)}
print(json.dumps(out, ensure_ascii=False), flush=True)
if not mp.framework:
    sys.exit(0)
existing = ar.repo_harness(ws.root, mp)
out["conftest_del_repo"] = bool(existing)
out["intentos"] = []
for attempt in range(3):
    try:
        prop = ar.generate(LLM(settings), ws.root, mp)
    except Exception as exc:
        out["intentos"].append("error: " + repr(exc)[:200]); continue
    code, out["modelo"] = prop.code, prop.model
    chk = ar.validate(code, mp, router._allowed(ws))
    out["intentos"].append("valido" if chk.valid else chk.errors[:2])
    if chk.valid:
        break
else:
    print(json.dumps(out, ensure_ascii=False, indent=1)); sys.exit(0)
(SCRATCH / f"{rid}.conftest.py").write_text(code, encoding="utf-8")
out["validacion"] = {"avisos": chk.warnings[:5], "fixtures": chk.fixtures}
print(json.dumps(out, ensure_ascii=False), flush=True)
if True:
    runner, reason = sandbox.start(settings, rid, "arnes", ar.overlay(code, mp))
    if runner is None:
        out["humo"] = {"status": "sin_sandbox", "motivo": reason}
    else:
        import asyncio
        async def go():
            phases = {}
            for name in ("venv", "install", "tests"):
                ph = await runner.wait(name)
                phases[name] = (ph.code, ph.log_tail)
            o = await asyncio.to_thread(runner.output)
            runner.close()
            return ar.read_smoke(o.junit, phases)
        res = asyncio.run(go())
        out["humo"] = {"status": res.status, "mensaje": res.message[:600], "pruebas": [(t.name, t.outcome) for t in res.tests]}
out["segundos"] = round(time.time() - t0)
print(json.dumps(out, ensure_ascii=False, indent=1))
