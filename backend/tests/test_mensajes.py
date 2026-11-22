"""Mensajes de los hallazgos de Ruff y Bandit en español (app/analyses/mensajes.py)."""

import pytest

from app.analyses.analyzers import static_findings
from app.analyses.mensajes import bandit_message, ruff_message


@pytest.mark.parametrize(
    ("original", "esperado"),
    [
        ("`os` imported but unused", "`os` se importa y no se usa"),
        ("Undefined name `total`", "El nombre `total` no está definido"),
        ("Local variable `x` is assigned to but never used", "La variable local `x` se asigna pero nunca se usa"),
        ("Do not use bare `except`", "No uses `except:` sin indicar la excepción"),
        ("Loop control variable `i` not used within loop body", "La variable del ciclo `i` no se usa dentro del ciclo"),
        ("Mensaje que no está en el catálogo", "Mensaje que no está en el catálogo"),
    ],
)
def test_traduce_mensajes_de_ruff(original, esperado):
    assert ruff_message(original) == esperado


def test_traduce_bandit_y_conserva_el_valor_de_la_contrasena():
    assert bandit_message("B101", "Use of assert detected.") == "Se usa `assert`: el código se elimina al compilar con optimización"
    assert bandit_message("B105", "Possible hardcoded password: 'abc'") == "Posible contraseña escrita en el código: 'abc'"
    # Un código que no está en el catálogo conserva el mensaje original
    assert bandit_message("B999", "Something new") == "Something new"


def test_los_hallazgos_salen_en_espanol():
    code = "import os\n\n\ndef f(items):\n    assert items\n    return [i for i in items]\n"
    found = static_findings(code, "app.py", None)
    messages = {f.rule: f.msg for f in found}
    assert messages["F401"] == "`os` se importa y no se usa"
    assert messages["B101"].startswith("Se usa `assert`")
