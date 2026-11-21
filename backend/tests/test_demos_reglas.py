"""
Repos demo de reglas de negocio (seed_data/inventario_demo y seed_data/reservas_demo,
docs/PROPUESTA_REGLAS_VERIFICABLES.md §11.1): sus reglas de referencia, sus pruebas escritas a mano y el veredicto
esperado de cada regla (referencia/ESPERADO.md de cada demo).
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.analyses import reglas
from app.projects import reglas_importar as importar

SEED = Path(__file__).resolve().parent.parent / "seed_data"
PLUGINS = Path(reglas.__file__).resolve().parent.parent / "analysis"


@dataclass(frozen=True)
class Demo:
    carpeta: str
    documento: str
    reglas: int
    rotas: frozenset[str]
    # Paquetes que el demo necesita y el backend no trae
    necesita: tuple[str, ...]

    @property
    def root(self) -> Path:
        return SEED / self.carpeta

    @property
    def referencia(self) -> str:
        return (self.root / "referencia" / "reglas_negocio.toml").read_text(encoding="utf-8")

    @property
    def esperado(self) -> dict[str, str]:
        ids = [f"RN-{n:03d}" for n in range(1, self.reglas + 1)]
        return {rid: "no_cumple" if rid in self.rotas else "cumple" for rid in ids}


DEMOS = [
    Demo("inventario_demo", "docs/Requerimientos.docx", 18, frozenset({"RN-001", "RN-006", "RN-015", "RN-017", "RN-018"}), ("sqlalchemy",)),
    Demo("reservas_demo", "docs/Requisitos.pdf", 15, frozenset({"RN-001", "RN-007", "RN-013", "RN-014"}), ("sqlalchemy", "flask")),
]
pytestmark = pytest.mark.parametrize("demo", DEMOS, ids=[d.carpeta for d in DEMOS])


def _files(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def _check(demo: Demo) -> reglas.RulesCheck:
    root = demo.root

    def lines(file: str) -> list[str] | None:
        try:
            return (root / file).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            return None

    return reglas.run(root, _files(root), lines, uploaded=demo.referencia)


def test_sin_reglas_en_el_repo_y_con_su_documento(demo):
    # Sin reglas_negocio.toml en la raíz ni en docs/: la app ofrece sacarlas del documento, que es el único detectado
    assert reglas.find(demo.root) is None
    sizes = {f: (demo.root / f).stat().st_size for f in _files(demo.root) if f.lower().endswith(importar.EXTENSIONS)}
    assert importar.find_documents(sizes) == [demo.documento]


def test_referencia_valida_sin_avisos_y_con_pruebas(demo):
    check = _check(demo)
    assert check.error is None and check.origin == "app" and check.warnings == []
    assert [r.rule.id for r in check.results] == list(demo.esperado)
    assert [r.rule.id for r in check.results if not r.tests] == []
    # Sin sandbox: todas quedan sin verificar, con sus pruebas encontradas leyendo el código
    assert {r.status for r in check.results} == {"sin_verificar"}


def test_veredictos_con_pytest(demo, tmp_path):
    for paquete in demo.necesita:
        pytest.importorskip(paquete, reason=f"el demo necesita {paquete} (uv run --with {' --with '.join(demo.necesita)} pytest …)")
    out = tmp_path / "reglas.json"
    env = {**os.environ, "PYTHONPATH": str(PLUGINS), "IA_VOY_REGLAS_OUT": str(out), "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "ia_voy_reglas"],
        cwd=demo.root, env=env, capture_output=True, text=True, timeout=300, check=False,
    )
    assert out.exists(), proc.stdout[-2000:] + proc.stderr[-2000:]
    data = json.loads(out.read_text(encoding="utf-8"))
    # Ninguna prueba falla al preparar (sería el arnés, no el código)
    assert [t["nodeid"] for t in data["tests"] if t["outcome"] == "error"] == []
    check = reglas.with_tests(_check(demo), data, None)
    assert {r.rule.id: r.status for r in check.results} == demo.esperado
