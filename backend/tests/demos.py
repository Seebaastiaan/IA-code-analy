"""
Los repos demo de reglas de negocio con su clave de respuestas.

`seed_data/<demo>` es el repo tal como se publica (como cualquier otro: código, interfaz, documento y README) y
`seed_data/<demo>_clave` lo que solo saben las pruebas (reglas resueltas, veredicto esperado, pruebas escritas a mano y su
arnés). Las pruebas que comparan contra la clave usan la copia combinada, que se arma una vez por proceso.
"""

import os
import shutil
import tempfile
from pathlib import Path

SEED = Path(__file__).resolve().parent.parent / "seed_data"
DEMOS = ("inventario_demo", "reservas_demo")
_ROOT = Path(tempfile.gettempdir()) / f"ia_voy_demos_{os.getpid()}"


def clean(name: str) -> Path:
    """El repo como se publica, sin la clave."""
    return SEED / name


def key(name: str) -> Path:
    return SEED / f"{name}_clave"


def combined(name: str) -> Path:
    """El demo con su clave encima (referencia/, tests/reglas/ y pytest.ini), en una carpeta temporal."""
    if not (_ROOT / ".listo").exists():
        shutil.rmtree(_ROOT, ignore_errors=True)
        for demo in DEMOS:
            dest = _ROOT / demo
            shutil.copytree(clean(demo), dest, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.db"))
            shutil.copytree(key(demo), dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "README.md"))
        (_ROOT / ".listo").write_text("", encoding="utf-8")
    return _ROOT / name
