"""
Mide los dos repos demo con Gemini real y Docker (PROPUESTA_REGLAS_VERIFICABLES.md §14.1): la evidencia de las 33 reglas
(¿señala la línea del error sembrado?) y la prueba de fuerza de las pruebas escritas a mano de las reglas que cumplen.

    cd backend && uv run python scripts/medir_demos.py [inventario_demo] [reservas_demo]

Requiere GEMINI_API_KEY en backend/.env y Docker corriendo. Escribe el resultado en ia_voy_medir/resultado.json, dentro de MEDIR_DIR
(por omisión, la carpeta temporal del sistema). El clon de cada demo se copia ahí; no se toca el repo.
"""
import ast
import asyncio
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

S = Path(os.environ.get("MEDIR_DIR") or tempfile.gettempdir()) / "ia_voy_medir"
S.mkdir(parents=True, exist_ok=True)
os.environ.update(CLONES_PATH=str(S / "clones"), SANDBOX="docker", DATABASE_PATH=str(S / "ia.db"))
os.environ.setdefault("SANDBOX_DOCKER_IMAGE", "ghcr.io/astral-sh/uv:python3.12-bookworm")
sys.path.insert(0, ".")
from app.analyses import mapa, reglas
from app.analysis import sandbox
from app.assistant.llm import LLM
from app.config import Settings
from app.projects import reglas_evidencia as evidencia
from app.projects import reglas_fuerza as fuerza

settings = Settings()
llm = LLM(settings)
SEED = Path("seed_data").resolve()
only = sys.argv[1:] or ["inventario_demo", "reservas_demo"]
report = {}


def seeded(esperado: str) -> dict[str, list[tuple[str, int]]]:
    out = {}
    for line in esperado.splitlines():
        m = re.match(r"\| (RN-\d{3}) \|", line)
        if m and "no cumple" in line:
            out[m.group(1)] = [(f, int(n)) for f, n in re.findall(r"\]\(\.\./\.\./\w+_demo/([^#)]+)#L(\d+)\)", line)]
    return out


def test_ids(root: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for path in sorted((root / "tests" / "reglas").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in tree.body:
            if not isinstance(fn, ast.FunctionDef):
                continue
            for d in fn.decorator_list:
                if isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "regla":
                    for a in d.args:
                        if isinstance(a, ast.Constant):
                            out.setdefault(a.value, []).append(f"tests/reglas/{path.name}::{fn.name}")
    return out


for name in only:
    # El demo como se publica, con las pruebas escritas a mano y su arnés de la clave (seed_data/<demo>_clave)
    src = SEED / f"{name}_clave"
    dest = S / "clones" / name
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(SEED / name, dest, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(src, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "referencia", "README.md"))
    mp = mapa.build(dest)
    rules = reglas.parse((src / "referencia/reglas_negocio.toml").read_text(encoding="utf-8")).rules
    esperado = (src / "referencia/ESPERADO.md").read_text(encoding="utf-8")
    bugs = seeded(esperado)
    ids = test_ids(dest)
    res = {"evidencia": {}, "fuerza": {}}
    t0 = time.time()
    for r in rules:
        for attempt in range(3):
            try:
                ev = evidencia.collect(llm, dest, mp, r)
                break
            except Exception as exc:  # límite de solicitudes, etc.
                print("   reintento", r.id, repr(exc)[:100], flush=True); time.sleep(20); ev = None
        if ev is None:
            res["evidencia"][r.id] = {"error": True}; continue
        hit = None
        if bugs.get(r.id):
            hit = any(p.file == f and p.start <= n <= p.end for p in ev.places for f, n in bugs[r.id])
        res["evidencia"][r.id] = {"veredicto": ev.verdict, "lugares": [(p.file, p.start, p.end) for p in ev.places], "sembrado": bugs.get(r.id), "senala": hit, "modelo": ev.model}
        res["evidencia"][r.id]["_ev"] = ev
        print(name, r.id, ev.verdict, "señala" if hit else ("NO señala" if hit is False else ""), flush=True)
    print(f"evidencia {name}: {round(time.time()-t0)} s", flush=True)

    # Prueba de fuerza de las pruebas buenas: reglas que cumplen y tienen pruebas
    good = [r for r in rules if r.id not in bugs and ids.get(r.id)]
    plan = {}
    for r in good:
        e = res["evidencia"][r.id].get("_ev")
        ms, found = fuerza.mutants(dest, mp, r, [], e, fuerza.MAX_MUTANTS, rules)
        plan[r.id] = (ms, found)
    batches, cur, count = [], [], 0
    for r in good:
        n = len(plan[r.id][0])
        if cur and count + n > fuerza.MAX_TOTAL:
            batches.append(cur); cur, count = [], 0
        cur.append(r.id); count += n
    if cur:
        batches.append(cur)
    for i, batch in enumerate(batches, 1):
        objectives = [(rid, ids[rid], plan[rid][0]) for rid in batch if plan[rid][0]]
        spec = fuerza.spec(objectives)
        shutil.copytree(dest, S / "clones" / f"{name}-{i}", dirs_exist_ok=True)
        runner, reason = sandbox.start(settings, f"{name}-{i}", "fuerza", {fuerza.SPEC: json.dumps(spec)})
        if runner is None:
            print("sin sandbox", reason); continue
        async def go():
            phases = {}
            for n in ("venv", "install", "tests"):
                ph = await runner.wait(n); phases[n] = (ph.code, ph.log_tail)
            o = runner.output(); runner.close(); return o, phases
        o, phases = asyncio.run(go())
        out = fuerza.read(o.fuerza, phases, {rid: plan[rid] for rid in batch})
        for rid, v in out.items():
            res["fuerza"][rid] = {"estado": v.status, "matados": v.killed, "total": v.total, "sobreviven": [(s.file, s.line, s.description) for s in v.survivors], "detalle": v.detail}
            print(name, rid, v.status, f"{v.killed}/{v.total}", flush=True)
    for v in res["evidencia"].values():
        v.pop("_ev", None)
    report[name] = res
    (S / "resultado.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
print("LISTO")
