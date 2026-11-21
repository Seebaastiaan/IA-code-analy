"""
Plugin de pytest de IA voy: nivel **pruebas** de las reglas de negocio (docs/adr/ADR-003-reglas-de-negocio.md).

Corre DENTRO del sandbox, con las pruebas del repo analizado: app.analysis.sandbox lo copia a la carpeta de
salida y lo carga con `PYTHONPATH=… pytest -p ia_voy_reglas`. Por eso no importa nada de `app` ni nada fuera
de la biblioteca estándar y pytest.

Una prueba verifica una regla si:
- lleva el marcador `@pytest.mark.regla("RN-002")` (admite varias: `regla("RN-001", "RN-004")`), en la
  función, en su clase o en `pytestmark` del módulo; o
- se llama `test_rn002_…` (nombre alternativo, sin marcador).

Al terminar escribe en `$IA_VOY_REGLAS_OUT` un JSON con cada prueba ligada y su resultado:
`{"version": 1, "tests": [{"nodeid", "file", "line", "rules", "outcome", "message"}]}` con `outcome` en
passed | failed | error | skipped | not_run. Registra el marcador para que pytest no avise (ni falle con
`--strict-markers`) en proyectos que no lo declararon.
"""

import json
import os
import re

NAME_RE = re.compile(r"^test_rn(\d{3})(?:_|$)", re.IGNORECASE)
ID_RE = re.compile(r"^RN-\d{3}$")
MAX_MESSAGE = 300
ENV_OUT = "IA_VOY_REGLAS_OUT"


def _ids(value: object) -> list[str]:
    if isinstance(value, str):
        return [value.strip().upper()]
    if isinstance(value, (list, tuple, set)):
        return [i for v in value for i in _ids(v)]
    return []


def rules_of(item) -> list[str]:
    """Reglas que verifica la prueba: las de sus marcadores `regla` y la de su nombre `test_rn###_…`."""
    ids: list[str] = []
    for mark in item.iter_markers(name="regla"):
        ids += _ids(list(mark.args))
    name = getattr(item, "originalname", None) or item.name
    match = NAME_RE.match(name)
    if match:
        ids.append(f"RN-{match.group(1)}")
    # Ordenadas (como app.analyses.reglas). Lo que no tiene formato RN-### también se reporta: el backend avisa
    return sorted({i for i in ids if i})


def _message(report) -> str:
    crash = getattr(report.longrepr, "reprcrash", None)
    text = getattr(crash, "message", None) or str(report.longrepr or "")
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[0][:MAX_MESSAGE] if lines else ""


class RulesCollector:
    def __init__(self) -> None:
        self.tests: dict[str, dict] = {}

    def pytest_collection_finish(self, session) -> None:
        # session.items: lo que va a correr (ya sin lo deseleccionado con -k / -m)
        for item in session.items:
            rules = rules_of(item)
            if not rules:
                continue
            path, line, _ = item.location
            self.tests[item.nodeid] = {
                "nodeid": item.nodeid,
                "file": str(path).replace("\\", "/"),
                # location viene desde 0
                "line": (line or 0) + 1,
                "rules": rules,
                "outcome": "not_run",
                "message": "",
            }

    def pytest_runtest_logreport(self, report) -> None:
        test = self.tests.get(report.nodeid)
        if test is None:
            return
        if report.failed:
            # La primera falla manda; una falla al preparar o al limpiar es un error, no una prueba que falla
            if test["outcome"] not in ("failed", "error"):
                test["outcome"] = "failed" if report.when == "call" else "error"
                test["message"] = _message(report)
        elif report.skipped:
            if test["outcome"] == "not_run":
                test["outcome"] = "skipped"
                test["message"] = _message(report)
        elif report.when == "call" and test["outcome"] == "not_run":
            test["outcome"] = "passed"

    def pytest_sessionfinish(self, session) -> None:
        out = os.environ.get(ENV_OUT)
        if not out:
            return
        try:
            with open(out, "w", encoding="utf-8") as f:
                json.dump({"version": 1, "tests": list(self.tests.values())}, f, ensure_ascii=False)
        except OSError:
            pass  # sin el archivo, el backend deja las reglas "sin verificar"


def pytest_configure(config) -> None:
    config.addinivalue_line("markers", "regla(*ids): regla de negocio de reglas_negocio.toml que verifica esta prueba (IA voy)")
    config.pluginmanager.register(RulesCollector(), "ia_voy_reglas_collector")
