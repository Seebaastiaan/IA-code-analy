"""
Mide qué tan estable es el diagnóstico con IA: corre POST /api/diagnostico varias veces sobre el MISMO
archivo y compara las respuestas (score, número de hallazgos, reglas y líneas citadas).

    python scripts/estabilidad_diagnostico.py --url https://github.com/equipo/api-pagos --file api.py --runs 10

Requiere el backend corriendo (uvicorn app.main:app) con GEMINI_API_KEY. Escribe una tabla Markdown que se
copia en docs/ia/estabilidad-diagnostico.md.
"""

import argparse
import statistics
import time
from itertools import combinations

import httpx


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


def run(api: str, url: str, branch: str, file: str | None, runs: int, pause: float) -> list[dict]:
    results = []
    with httpx.Client(timeout=120) as http:
        for i in range(runs):
            start = time.monotonic()
            res = http.post(f"{api}/api/diagnostico", json={"url": url, "branch": branch, "file": file})
            seconds = round(time.monotonic() - start, 1)
            if res.status_code != 200:
                print(f"corrida {i + 1}: error {res.status_code} {res.text[:200]}")
                continue
            diag = res.json()["diagnostico"]
            results.append({
                "score": diag["score"],
                "hallazgos": len(diag["hallazgos"]),
                "reglas": {h["regla"] for h in diag["hallazgos"]},
                "lineas": {(h["regla"], h["linea"]) for h in diag["hallazgos"]},
                "segundos": seconds,
            })
            print(f"corrida {i + 1}: score {diag['score']} · {len(diag['hallazgos'])} hallazgos · {seconds} s")
            time.sleep(pause)
    return results


def report(results: list[dict]) -> str:
    scores = [r["score"] for r in results]
    counts = [r["hallazgos"] for r in results]
    pairs = list(combinations(results, 2))
    rules = statistics.mean(jaccard(a["reglas"], b["reglas"]) for a, b in pairs) if pairs else 1.0
    lines = statistics.mean(jaccard(a["lineas"], b["lineas"]) for a, b in pairs) if pairs else 1.0
    rows = [
        "| Métrica | Valor |",
        "|---|---|",
        f"| Corridas válidas | {len(results)} |",
        f"| Score (mín · máx · desviación) | {min(scores)} · {max(scores)} · {statistics.pstdev(scores):.1f} |",
        f"| Hallazgos por corrida (mín · máx) | {min(counts)} · {max(counts)} |",
        f"| Coincidencia de reglas entre corridas (Jaccard) | {rules:.2f} |",
        f"| Coincidencia de regla + línea (Jaccard) | {lines:.2f} |",
        f"| Tiempo medio por corrida | {statistics.mean(r['segundos'] for r in results):.1f} s |",
    ]
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Estabilidad del diagnóstico con IA")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--url", required=True)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--file", default=None)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--pause", type=float, default=4.0, help="segundos entre corridas (cuota de la API)")
    args = parser.parse_args()
    results = run(args.api, args.url, args.branch, args.file, args.runs, args.pause)
    if len(results) < 2:
        raise SystemExit("Se necesitan al menos dos corridas válidas")
    print()
    print(report(results))


if __name__ == "__main__":
    main()
