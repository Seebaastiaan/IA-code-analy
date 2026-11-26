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
`{"version": 2, "tests": [{"nodeid", "file", "line", "rules", "outcome", "message", "exception"}]}` con `outcome` en
passed | failed | error | skipped | not_run y `exception` = tipo de la excepción que la hizo fallar
("AssertionError", "PreparacionFallida", "KeyError"…). Con él el backend separa «no cumple» (falló un `assert`) de
«prueba rota» (falló la preparación, un import o cualquier otra excepción, PROPUESTA_REGLAS_VERIFICABLES.md §9). Registra el marcador para que pytest no avise (ni falle con
`--strict-markers`) en proyectos que no lo declararon.

Con `IA_VOY_SIN_RED=1` (pruebas del arnés, generadas y de fuerza, PROPUESTA §7.3) **bloquea la red**: una conexión o
una consulta DNS a un host que no sea local lanza `RedBloqueada` y la prueba queda como rota (`exception =
"RedBloqueada"`) aunque el código haya atrapado el error. Nunca sale nada a internet; las integraciones se sustituyen
con los fakes del arnés (`buzon`, `respx`, `responses`).
"""

import json
import os
import re

NAME_RE = re.compile(r"^test_rn(\d{3})(?:_|$)", re.IGNORECASE)
ID_RE = re.compile(r"^RN-\d{3}$")
MAX_MESSAGE = 300
ENV_OUT = "IA_VOY_REGLAS_OUT"
ENV_NO_NET = "IA_VOY_SIN_RED"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "testserver", ""}


class RedBloqueada(Exception):
    """La prueba intentó salir a la red (IA voy la bloquea): la prueba está rota, no el código."""


# Intentos de salir a la red durante la prueba en curso
_attempts: list[str] = []


def _local(host) -> bool:
    if host is None:
        return True
    host = host.decode() if isinstance(host, bytes) else str(host)
    return host.lower() in LOCAL_HOSTS or host.startswith("127.")


def _blocked(what: str) -> RedBloqueada:
    message = f"la prueba intentó salir a la red ({what}); usa los fakes del arnés (buzon, respx, responses)"
    _attempts.append(message)
    return RedBloqueada(message)


def block_network() -> None:
    """Sustituye connect y getaddrinfo de `socket`: lo local (y los sockets Unix) sigue funcionando."""
    import socket

    real_connect, real_connect_ex, real_getaddrinfo = socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo

    def _check(sock, address) -> None:
        if sock.family in (socket.AF_INET, socket.AF_INET6) and isinstance(address, tuple) and not _local(address[0]):
            raise _blocked(f"{address[0]}:{address[1]}")

    def connect(self, address):
        _check(self, address)
        return real_connect(self, address)

    def connect_ex(self, address):
        _check(self, address)
        return real_connect_ex(self, address)

    def getaddrinfo(host, *args, **kwargs):
        if not _local(host):
            raise _blocked(str(host))
        return real_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = getaddrinfo


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
                "exception": "",
            }

    def pytest_runtest_setup(self, item) -> None:
        _attempts.clear()

    def pytest_runtest_makereport(self, item, call) -> None:
        """Guarda el tipo de la excepción (el reporte solo trae el texto). No devuelve nada: pytest arma el reporte."""
        test = self.tests.get(item.nodeid)
        if test is not None and call.excinfo is not None and not test["exception"]:
            test["exception"] = call.excinfo.typename

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
        # Intentó salir a la red: rota aunque el código haya atrapado el error (y aunque la prueba haya pasado)
        if report.when == "call" and _attempts and test["exception"] != "RedBloqueada":
            test["outcome"], test["exception"], test["message"] = "failed", "RedBloqueada", _attempts[0][:MAX_MESSAGE]

    def pytest_sessionfinish(self, session) -> None:
        out = os.environ.get(ENV_OUT)
        if not out:
            return
        try:
            with open(out, "w", encoding="utf-8") as f:
                json.dump({"version": 2, "tests": list(self.tests.values())}, f, ensure_ascii=False)
        except OSError:
            pass  # sin el archivo, el backend deja las reglas "sin verificar"


def pytest_configure(config) -> None:
    config.addinivalue_line("markers", "regla(*ids): regla de negocio de reglas_negocio.toml que verifica esta prueba (IA voy)")
    config.pluginmanager.register(RulesCollector(), "ia_voy_reglas_collector")
    if os.environ.get(ENV_NO_NET) == "1":
        block_network()
