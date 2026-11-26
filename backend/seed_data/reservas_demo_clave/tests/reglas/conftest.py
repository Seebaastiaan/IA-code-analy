"""
Arnés de las pruebas de reglas de negocio (docs/PROPUESTA_REGLAS_VERIFICABLES.md §7 de IA voy).

Mismos nombres que usarán las pruebas generadas: `api`, `como(rol)`, `crear_cliente(...)`, `reservar(...)`,
`preparar(...)`, `reloj` (hora fija, se mueve con `reloj.ir_a(...)` / `reloj.avanzar(...)`) y `buzon` (los correos
que la app "envió"; nunca sale nada a la red). Cada prueba tiene su propia base SQLite en memoria.
"""

from datetime import datetime, timedelta
from itertools import count

import pytest
from werkzeug.security import generate_password_hash

from reservas import correo, db, reloj as reloj_app
from reservas.app import crear_app
from reservas.modelos import Usuario

# Martes 1 de diciembre de 2026, 8:00: las pruebas reservan de ahí en adelante
AHORA = datetime(2026, 12, 1, 8, 0)
CLAVE = "clave-de-prueba"


class PreparacionFallida(Exception):
    """El *Dado* del escenario no se pudo preparar: la prueba está rota, no el código."""


def preparar(condicion: bool, motivo: str) -> None:
    if not condicion:
        raise PreparacionFallida(motivo)


class Reloj:
    def __init__(self, momento: datetime) -> None:
        self.momento = momento

    def ahora(self) -> datetime:
        return self.momento

    def ir_a(self, momento: datetime) -> None:
        self.momento = momento

    def avanzar(self, **delta) -> None:
        self.momento += timedelta(**delta)


@pytest.fixture
def reloj(monkeypatch) -> Reloj:
    r = Reloj(AHORA)
    monkeypatch.setattr(reloj_app, "ahora", r.ahora)
    return r


@pytest.fixture
def buzon(monkeypatch) -> list[dict]:
    enviados: list[dict] = []
    monkeypatch.setattr(correo, "_entregar", lambda m: enviados.append({"para": m["To"], "asunto": m["Subject"], "cuerpo": m.get_content()}))
    return enviados


@pytest.fixture
def app(reloj, buzon):
    aplicacion = crear_app("sqlite://")
    # Un error del servidor llega como respuesta 500 (el código falló), no como excepción de la prueba
    aplicacion.config.update(PROPAGATE_EXCEPTIONS=False)
    return aplicacion


class Cliente:
    """Cliente HTTP con el token de un usuario."""

    def __init__(self, http, token: str | None, usuario: dict) -> None:
        self.http = http
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.usuario = usuario

    def __getattr__(self, metodo: str):
        if metodo not in ("get", "post", "patch", "put", "delete"):
            raise AttributeError(metodo)
        return lambda ruta, **kw: getattr(self.http, metodo)(ruta, headers=self.headers, **kw)


def _usuario(rol: str, n: int, premium: bool = False) -> dict:
    with db.sesion() as s:
        u = Usuario(
            nombre=f"{rol.capitalize()} {n}", email=f"{rol}{n}@prueba.example", clave_hash=generate_password_hash(CLAVE, method="pbkdf2:sha256:1000"),
            rol=rol, premium=premium, token=f"prueba-{rol}-{n}",
        )
        s.add(u)
        s.commit()
        return {"id": u.id, "nombre": u.nombre, "email": u.email, "token": u.token}


@pytest.fixture
def clave() -> str:
    """Contraseña de todos los usuarios de prueba (hash rápido: solo para pruebas)."""
    return CLAVE


@pytest.fixture
def api(app) -> Cliente:
    """Sin usuario."""
    return Cliente(app.test_client(), None, {})


@pytest.fixture
def crear_cliente(app):
    """Un cliente nuevo (cada llamada es otra persona). Devuelve su `Cliente` HTTP; sus datos en `.usuario`."""
    folio = count(1)

    def crear(premium: bool = False) -> Cliente:
        u = _usuario("cliente", next(folio), premium)
        return Cliente(app.test_client(), u["token"], u)

    return crear


@pytest.fixture
def como(app, crear_cliente):
    """`como("recepcion")`: siempre el mismo usuario de ese rol. `como("cliente")` = un cliente fijo."""
    usuarios: dict[str, Cliente] = {}

    def cliente(rol: str) -> Cliente:
        if rol not in usuarios:
            usuarios[rol] = crear_cliente() if rol == "cliente" else Cliente(app.test_client(), (u := _usuario(rol, 1))["token"], u)
        return usuarios[rol]

    return cliente


@pytest.fixture
def servicio(como) -> dict:
    """Masaje de 60 min a $800 (anticipo $240)."""
    r = como("admin").post("/servicios", json={"nombre": "Masaje relajante", "duracion_min": 60, "precio": "800"})
    preparar(r.status_code == 201, f"no se pudo crear el servicio: {r.status_code} {r.get_data(as_text=True)}")
    return r.get_json()


@pytest.fixture
def crear_profesional(como):
    folio = count(1)

    def crear() -> dict:
        r = como("admin").post("/profesionales", json={"nombre": f"Terapeuta {next(folio)}"})
        preparar(r.status_code == 201, f"no se pudo crear el profesional: {r.status_code}")
        return r.get_json()

    return crear


@pytest.fixture
def profesional(crear_profesional) -> dict:
    return crear_profesional()


@pytest.fixture
def reservar(servicio, profesional):
    """Respuesta de reservar `inicio` como `quien`. Usa el masaje y el profesional por defecto si no se indican."""

    def hacer(quien: Cliente, inicio: datetime, servicio_=None, profesional_=None, **extra):
        datos = {"servicio_id": (servicio_ or servicio)["id"], "profesional_id": (profesional_ or profesional)["id"], "inicio": inicio.isoformat(), **extra}
        return quien.post("/citas", json=datos)

    return hacer


@pytest.fixture
def cita(reservar, como):
    """Reserva que debe salir bien (si no, la prueba está rota). Devuelve la cita."""

    def hacer(quien=None, inicio: datetime = datetime(2026, 12, 3, 10, 0), **kw) -> dict:
        r = reservar(quien or como("cliente"), inicio, **kw)
        preparar(r.status_code == 201, f"la reserva no se hizo: {r.status_code} {r.get_data(as_text=True)}")
        return r.get_json()

    return hacer
