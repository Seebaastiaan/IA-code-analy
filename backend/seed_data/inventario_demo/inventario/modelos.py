"""Tablas del inventario."""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from inventario.db import Base


class Numero(TypeDecorator):
    """Decimal guardado como texto: SQLite no tiene un tipo decimal exacto y REAL pierde centavos."""

    impl = String(40)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else str(Decimal(value))

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value)


def ahora() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))
    # cajero | barista | gerente | almacenista
    rol: Mapped[str] = mapped_column(String(20))
    token: Mapped[str] = mapped_column(String(80), unique=True)


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(40), unique=True)
    codigo_barras: Mapped[str] = mapped_column(String(40), unique=True)
    nombre_interno: Mapped[str] = mapped_column(String(120))
    # Nombre sin mayúsculas ni espacios repetidos, para que no se repita
    nombre_clave: Mapped[str] = mapped_column(String(120), unique=True)
    # reventa | compuesto | insumo
    tipo: Mapped[str] = mapped_column(String(20))
    # pieza | g | ml
    unidad_base: Mapped[str] = mapped_column(String(10))
    unidad_compra: Mapped[str] = mapped_column(String(20))
    # Unidades base que trae una unidad de compra (1 costal = 1000 g)
    factor_compra: Mapped[Decimal] = mapped_column(Numero)
    precio_base: Mapped[Decimal] = mapped_column(Numero)
    iva_tasa: Mapped[Decimal] = mapped_column(Numero)
    ieps_tasa: Mapped[Decimal] = mapped_column(Numero)
    # Costo promedio de una unidad base
    costo_unitario: Mapped[Decimal] = mapped_column(Numero)
    stock_actual: Mapped[Decimal] = mapped_column(Numero)
    stock_minimo: Mapped[Decimal] = mapped_column(Numero)
    # activo | inactivo
    estado: Mapped[str] = mapped_column(String(10), default="activo")
    requiere_reabastecer: Mapped[bool] = mapped_column(Boolean, default=False)

    movimientos: Mapped[list["Movimiento"]] = relationship(back_populates="producto", cascade="all, delete-orphan")
    lotes: Mapped[list["Lote"]] = relationship(back_populates="producto", cascade="all, delete-orphan")
    receta: Mapped[list["RecetaInsumo"]] = relationship(foreign_keys="RecetaInsumo.producto_id", cascade="all, delete-orphan")


class Lote(Base):
    __tablename__ = "lotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    fecha_entrada: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    caducidad: Mapped[date | None] = mapped_column(Date, nullable=True)
    cantidad_inicial: Mapped[Decimal] = mapped_column(Numero)
    cantidad_disponible: Mapped[Decimal] = mapped_column(Numero)
    costo_unitario: Mapped[Decimal] = mapped_column(Numero)

    producto: Mapped[Producto] = relationship(back_populates="lotes")


class Movimiento(Base):
    """Renglón del Kardex: cada cambio de existencias deja uno."""

    __tablename__ = "movimientos"

    id: Mapped[int] = mapped_column(primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    # entrada | venta | consumo_receta | merma | ajuste
    tipo: Mapped[str] = mapped_column(String(20))
    # Positiva si entra, negativa si sale
    cantidad: Mapped[Decimal] = mapped_column(Numero)
    saldo: Mapped[Decimal] = mapped_column(Numero)
    costo_unitario: Mapped[Decimal] = mapped_column(Numero)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    motivo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    lote_id: Mapped[int | None] = mapped_column(ForeignKey("lotes.id"), nullable=True)
    venta_id: Mapped[int | None] = mapped_column(ForeignKey("ventas.id"), nullable=True)

    producto: Mapped[Producto] = relationship(back_populates="movimientos")
    usuario: Mapped[Usuario] = relationship()


class RecetaInsumo(Base):
    __tablename__ = "receta_insumos"

    id: Mapped[int] = mapped_column(primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    insumo_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    # En la unidad base del insumo, por cada unidad vendida del producto
    cantidad: Mapped[Decimal] = mapped_column(Numero)

    insumo: Mapped[Producto] = relationship(foreign_keys=[insumo_id])


class Venta(Base):
    __tablename__ = "ventas"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    total: Mapped[Decimal] = mapped_column(Numero)

    lineas: Mapped[list["VentaLinea"]] = relationship(cascade="all, delete-orphan")


class VentaLinea(Base):
    __tablename__ = "venta_lineas"

    id: Mapped[int] = mapped_column(primary_key=True)
    venta_id: Mapped[int] = mapped_column(ForeignKey("ventas.id"))
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    cantidad: Mapped[Decimal] = mapped_column(Numero)
    precio_unitario: Mapped[Decimal] = mapped_column(Numero)
    importe: Mapped[Decimal] = mapped_column(Numero)


class Alerta(Base):
    __tablename__ = "alertas"

    id: Mapped[int] = mapped_column(primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    tipo: Mapped[str] = mapped_column(String(30))
    mensaje: Mapped[str] = mapped_column(String(200))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    atendida: Mapped[bool] = mapped_column(Boolean, default=False)


class Auditoria(Base):
    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    entidad: Mapped[str] = mapped_column(String(30))
    entidad_id: Mapped[int]
    campo: Mapped[str] = mapped_column(String(40))
    valor_anterior: Mapped[str | None] = mapped_column(String(80), nullable=True)
    valor_nuevo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
