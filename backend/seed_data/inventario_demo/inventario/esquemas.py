"""Entradas y salidas de la API."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Tipo = Literal["reventa", "compuesto", "insumo"]
Unidad = Literal["pieza", "g", "ml"]


class ProductoNuevo(BaseModel):
    sku: str = Field(min_length=1, max_length=40)
    codigo_barras: str = Field(min_length=1, max_length=40)
    nombre_interno: str = Field(min_length=1, max_length=120)
    tipo: Tipo = "reventa"
    unidad_base: Unidad = "pieza"
    unidad_compra: str = Field(default="pieza", min_length=1, max_length=20)
    factor_compra: Decimal = Field(default=Decimal(1), gt=0)
    precio_base: Decimal = Field(gt=0)
    iva_tasa: Decimal = Field(default=Decimal("0.16"), ge=0, le=1)
    ieps_tasa: Decimal = Field(default=Decimal(0), ge=0, le=1)
    costo_unitario: Decimal = Field(default=Decimal(0), ge=0)
    stock_minimo: Decimal = Field(default=Decimal(0), ge=0)


class ProductoCambios(BaseModel):
    """Lo que se puede editar de un producto. Las existencias cambian con movimientos, no aquí."""

    nombre_interno: str | None = Field(default=None, min_length=1, max_length=120)
    unidad_base: Unidad | None = None
    unidad_compra: str | None = Field(default=None, min_length=1, max_length=20)
    factor_compra: Decimal | None = Field(default=None, gt=0)
    precio_base: Decimal | None = Field(default=None, gt=0)
    iva_tasa: Decimal | None = Field(default=None, ge=0, le=1)
    ieps_tasa: Decimal | None = Field(default=None, ge=0, le=1)
    costo_unitario: Decimal | None = Field(default=None, ge=0)
    stock_minimo: Decimal | None = Field(default=None, ge=0)


class Impuestos(BaseModel):
    iva_tasa: Decimal
    ieps_tasa: Decimal
    ieps: Decimal
    iva: Decimal


class ProductoSalida(BaseModel):
    id: int
    sku: str
    codigo_barras: str
    nombre_interno: str
    tipo: str
    unidad_base: str
    unidad_compra: str
    factor_compra: Decimal
    precio_base: Decimal
    impuestos: Impuestos
    precio_con_impuestos: Decimal
    costo_unitario: Decimal
    stock_actual: Decimal
    stock_minimo: Decimal
    estado: str
    requiere_reabastecer: bool
    avisos: list[str] = []


class InsumoReceta(BaseModel):
    insumo_id: int
    cantidad: Decimal = Field(gt=0)


class Receta(BaseModel):
    insumos: list[InsumoReceta] = Field(min_length=1)


class Compra(BaseModel):
    producto_id: int
    # En unidades de compra (cajas, costales…)
    cantidad: Decimal = Field(gt=0)
    # Costo de una unidad de compra
    costo_unitario: Decimal = Field(ge=0)
    caducidad: date | None = None
    fecha_entrada: datetime | None = None


class LineaVenta(BaseModel):
    producto_id: int
    cantidad: Decimal = Field(gt=0)


class NuevaVenta(BaseModel):
    lineas: list[LineaVenta] = Field(min_length=1)


class Merma(BaseModel):
    producto_id: int
    cantidad: Decimal = Field(gt=0)
    motivo: str = Field(min_length=1, max_length=200)


class Ajuste(BaseModel):
    producto_id: int
    # Positiva si sobra, negativa si falta (conteo físico)
    cantidad: Decimal
    motivo: str = Field(min_length=1, max_length=200)


class MovimientoSalida(BaseModel):
    id: int
    tipo: str
    cantidad: Decimal
    saldo: Decimal
    costo_unitario: Decimal
    usuario_id: int
    usuario: str
    fecha: datetime
    motivo: str | None
    lote_id: int | None


class LoteSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha_entrada: datetime
    caducidad: date | None
    cantidad_inicial: Decimal
    cantidad_disponible: Decimal
    costo_unitario: Decimal


class CompraSalida(BaseModel):
    lote_id: int
    movimiento_id: int
    producto: ProductoSalida


class VentaSalida(BaseModel):
    venta_id: int
    total: Decimal


class AlertaSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    producto_id: int
    tipo: str
    mensaje: str
    fecha: datetime
    atendida: bool


class AuditoriaSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entidad: str
    entidad_id: int
    campo: str
    valor_anterior: str | None
    valor_nuevo: str | None
    usuario_id: int
    fecha: datetime
