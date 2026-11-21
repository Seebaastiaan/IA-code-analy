"""
Ejecutor de la prueba de fuerza de IA voy (app.projects.reglas_fuerza, PROPUESTA_REGLAS_VERIFICABLES.md §12.2, fase 5).

Corre DENTRO del sandbox, en la copia temporal del repo (app.analysis.sandbox lo copia a OUT/plugins). Solo usa la
biblioteca estándar. Uso: `python ia_voy_fuerza.py MUTANTES.json SALIDA.json`.

MUTANTES.json = {"objetivos": [{"regla", "prueba", "mutantes": [{"id", "archivo", "codigo"}]}]}. Por cada objetivo:
1. corre la prueba de la regla con el código original (debe pasar: si no, la prueba de fuerza no aplica);
2. por cada mutante, escribe el archivo mutado, corre la prueba y restaura el original.
Un mutante **muere** si la prueba falla (código de salida distinto de 0, o se agota el tiempo); si sigue pasando,
la prueba no notó el cambio. Escribe en SALIDA.json `{"version": 1, "objetivos": [{"regla", "base", "mutantes":
[{"id", "codigo_salida", "segundos"}]}]}`.
"""

import json
import os
import subprocess  # nosec B404 — corre pytest en el sandbox, sobre la copia temporal
import sys
import time
from pathlib import Path

TIMEOUT_S = 90
TIMEOUT_CODE = 124


def _pytest(target: str) -> int:
    cmd = [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "-o", "addopts=", "-p", "ia_voy_reglas", target]
    try:
        return subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=TIMEOUT_S, check=False).returncode  # nosec B603
    except subprocess.TimeoutExpired:
        return TIMEOUT_CODE


def run(spec: dict, root: Path) -> dict:
    out = []
    for obj in spec.get("objetivos") or []:
        target = str(obj.get("prueba") or "")
        base = _pytest(target)
        result = {"regla": obj.get("regla"), "base": base, "mutantes": []}
        out.append(result)
        if base != 0:
            continue
        for m in obj.get("mutantes") or []:
            path = (root / str(m.get("archivo") or "")).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                result["mutantes"].append({"id": m.get("id"), "codigo_salida": None, "segundos": 0})
                continue
            original = path.read_bytes()
            start = time.monotonic()
            try:
                path.write_text(str(m.get("codigo") or ""), encoding="utf-8")
                code = _pytest(target)
            finally:
                path.write_bytes(original)
            result["mutantes"].append({"id": m.get("id"), "codigo_salida": code, "segundos": round(time.monotonic() - start, 2)})
    return {"version": 1, "objetivos": out}


def main(argv: list[str]) -> int:
    spec_path, out_path = Path(argv[1]), Path(argv[2])
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    # Las pruebas no salen a la red (el plugin ia_voy_reglas la bloquea con esta variable)
    os.environ.setdefault("IA_VOY_SIN_RED", "1")
    result = run(spec, Path.cwd().resolve())
    out_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
