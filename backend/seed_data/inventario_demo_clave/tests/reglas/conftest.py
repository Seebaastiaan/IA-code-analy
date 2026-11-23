"""
Arnés de las pruebas de reglas de negocio (docs/PROPUESTA_REGLAS_VERIFICABLES.md §7 de IA voy).

Los nombres de los fixtures son los que usarán las pruebas generadas: `api`, `como(rol)`, `crear_producto(...)`,
`comprar(...)`, `vender(...)` y `preparar(...)`. Cada prueba tiene su propia base SQLite en memoria.
"""

from datetime import datetime
from decimal import Decimal
from itertools import count

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from inventario.db import Base, get_db
from inventario.main import app
from inventario.modelos import Usuario


class PreparacionFallida(Exception):
    """El *Dado* del escenario no se pudo preparar: la prueba está rota, no el código."""


def preparar(condicion: bool, motivo: str) -> None:
    if not condicion:
        raise PreparacionFallida(motivo)


@pytest.fixture
def sesiones():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine, expire_on_commit=False)

    def db():
        with fabrica() as session:
            yield session

    app.dependency_overrides[get_db] = db
    yield fabrica
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def api(sesiones) -> TestClient:
    """Cliente sin usuario. Sin `with`: no corre el arranque de la app (que usa la base real)."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def como(sesiones):
    """`como("cajero")`: cliente autenticado con un usuario de ese rol (se crea la primera vez)."""
    clientes: dict[str, TestClient] = {}

    def cliente(rol: str) -> TestClient:
        if rol not in clientes:
            with sesiones() as db:
                usuario = Usuario(nombre=f"Usuario {rol}", rol=rol, token=f"prueba-{rol}")
                db.add(usuario)
                db.commit()
                nuevo = TestClient(app, headers={"Authorization": f"Bearer prueba-{rol}"}, raise_server_exceptions=False)
                # El id de su usuario, para las rutas que lo piden en el cuerpo
                nuevo.id = usuario.id
            clientes[rol] = nuevo
        return clientes[rol]

    return cliente


@pytest.fixture
def usuario_id(sesiones, como):
    """Id del usuario de un rol (lo crea si hace falta)."""

    def buscar(rol: str) -> int:
        como(rol)
        with sesiones() as db:
            return db.query(Usuario).filter_by(rol=rol).one().id

    return buscar


@pytest.fixture
def comprar(como):
    """Registra una compra como almacenista. `cantidad` va en unidades de compra."""

    def hacer(producto: dict, cantidad, costo="10", **extra) -> dict:
        datos = {"producto_id": producto["id"], "cantidad": str(cantidad), "costo_unitario": str(costo)}
        for clave, valor in extra.items():
            datos[clave] = valor.isoformat() if isinstance(valor, datetime) else str(valor)
        r = como("almacenista").post("/compras", json=datos)
        preparar(r.status_code == 201, f"la compra no se registró: {r.status_code} {r.text}")
        return r.json()

    return hacer


@pytest.fixture
def crear_producto(como, comprar):
    """
    Crea un producto como gerente. `stock_actual=` lo deja con esas existencias con una compra (nunca editando el
    stock); `costo_compra=` es el costo de esa compra por unidad de compra.
    """
    folio = count(1)

    def crear(stock_actual=None, costo_compra="10", **campos) -> dict:
        n = next(folio)
        datos = {"sku": f"SKU-{n:03d}", "codigo_barras": f"75000000{n:04d}", "nombre_interno": f"Producto {n}", "precio_base": "20"}
        datos.update({k: str(v) if isinstance(v, (int, float, Decimal)) else v for k, v in campos.items()})
        r = como("gerente").post("/productos", json=datos)
        preparar(r.status_code == 201, f"no se pudo crear el producto: {r.status_code} {r.text}")
        producto = r.json()
        if stock_actual:
            factor = Decimal(producto["factor_compra"])
            comprar(producto, Decimal(str(stock_actual)) / factor, costo_compra)
        return como("gerente").get(f"/productos/{producto['id']}").json()

    return crear


@pytest.fixture
def vender(como):
    def hacer(producto: dict, cantidad, rol="cajero"):
        return como(rol).post("/ventas", json={"lineas": [{"producto_id": producto["id"], "cantidad": str(cantidad)}]})

    return hacer


def dec(valor) -> Decimal:
    return Decimal(str(valor))
