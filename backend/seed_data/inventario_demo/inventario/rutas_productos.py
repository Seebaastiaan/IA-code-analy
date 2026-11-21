"""Catálogo: alta, consulta, edición, baja, receta, lotes y Kardex de cada producto."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from inventario.auth import Actual, Db, requiere
from inventario.esquemas import LoteSalida, MovimientoSalida, ProductoCambios, ProductoNuevo, ProductoSalida, Receta
from inventario.modelos import Lote, Movimiento, Producto, RecetaInsumo, Usuario
from inventario.servicios import auditar, dinero, normalizar_nombre, obtener, salida, tiene_movimientos

router = APIRouter(prefix="/productos", tags=["productos"])

CATALOGO = ("gerente", "almacenista")
PRECIOS = ("gerente", "cajero")
CAMPOS_PRECIO = {"precio_base", "costo_unitario", "iva_tasa", "ieps_tasa"}
DINERO = {"precio_base", "costo_unitario"}
ETIQUETAS = {"sku": "SKU", "codigo_barras": "código de barras", "nombre_clave": "nombre interno"}


def _unicos(db: Session, excluir: int | None = None, **campos: str) -> None:
    for campo, valor in campos.items():
        consulta = select(Producto.id).where(getattr(Producto, campo) == valor)
        if excluir is not None:
            consulta = consulta.where(Producto.id != excluir)
        if db.scalar(consulta) is not None:
            raise HTTPException(409, f"Ya existe un producto con ese {ETIQUETAS[campo]}")


@router.post("", status_code=201, response_model=ProductoSalida)
def crear(datos: ProductoNuevo, db: Db, usuario: Annotated[Usuario, Depends(requiere(*CATALOGO))]) -> ProductoSalida:
    clave = normalizar_nombre(datos.nombre_interno)
    _unicos(db, sku=datos.sku.strip(), codigo_barras=datos.codigo_barras.strip(), nombre_clave=clave)
    valores = datos.model_dump()
    valores.update(
        sku=datos.sku.strip(), codigo_barras=datos.codigo_barras.strip(), nombre_interno=" ".join(datos.nombre_interno.split()),
        precio_base=dinero(datos.precio_base), costo_unitario=dinero(datos.costo_unitario),
    )
    producto = Producto(**valores, nombre_clave=clave, stock_actual=Decimal(0), estado="activo", requiere_reabastecer=False)
    db.add(producto)
    db.commit()
    return salida(producto)


@router.get("", response_model=list[ProductoSalida])
def listar(db: Db, usuario: Actual, incluir_inactivos: bool = False) -> list[ProductoSalida]:
    consulta = select(Producto).order_by(Producto.id)
    if not incluir_inactivos:
        consulta = consulta.where(Producto.estado == "activo")
    return [salida(p) for p in db.scalars(consulta)]


@router.get("/{producto_id}", response_model=ProductoSalida)
def consultar(producto_id: int, db: Db, usuario: Actual) -> ProductoSalida:
    return salida(obtener(db, producto_id))


@router.patch("/{producto_id}", response_model=ProductoSalida)
def editar(producto_id: int, cambios: ProductoCambios, db: Db, usuario: Actual) -> ProductoSalida:
    producto = obtener(db, producto_id)
    datos = cambios.model_dump(exclude_unset=True, exclude_none=True)
    if datos.keys() & CAMPOS_PRECIO and usuario.rol not in PRECIOS:
        raise HTTPException(403, f"El rol {usuario.rol} no puede cambiar precios ni costos")
    if datos.keys() - CAMPOS_PRECIO and usuario.rol not in CATALOGO:
        raise HTTPException(403, f"El rol {usuario.rol} no puede editar el catálogo")
    if "nombre_interno" in datos:
        clave = normalizar_nombre(datos["nombre_interno"])
        _unicos(db, excluir=producto.id, nombre_clave=clave)
        producto.nombre_clave = clave
        datos["nombre_interno"] = " ".join(datos["nombre_interno"].split())
    if datos.get("unidad_base", producto.unidad_base) != producto.unidad_base and tiene_movimientos(db, producto):
        raise HTTPException(409, "La unidad base no se cambia: el producto ya tiene movimientos")
    for campo, valor in datos.items():
        if campo in DINERO:
            valor = dinero(valor)
        setattr(producto, campo, valor)
        if campo in CAMPOS_PRECIO:
            auditar(db, usuario, "producto", producto.id, campo, getattr(producto, campo), valor)
    db.commit()
    return salida(producto)


@router.delete("/{producto_id}", status_code=204)
def eliminar(producto_id: int, db: Db, usuario: Annotated[Usuario, Depends(requiere("gerente"))]) -> Response:
    producto = obtener(db, producto_id)
    db.delete(producto)
    db.commit()
    return Response(status_code=204)


@router.put("/{producto_id}/receta", response_model=ProductoSalida)
def definir_receta(producto_id: int, receta: Receta, db: Db, usuario: Annotated[Usuario, Depends(requiere("gerente"))]) -> ProductoSalida:
    producto = obtener(db, producto_id)
    if producto.tipo != "compuesto":
        raise HTTPException(409, "Solo un producto compuesto tiene receta")
    producto.receta.clear()
    for item in receta.insumos:
        insumo = obtener(db, item.insumo_id)
        if insumo.tipo == "compuesto" or insumo.id == producto.id:
            raise HTTPException(409, f"{insumo.nombre_interno} no puede ser insumo")
        producto.receta.append(RecetaInsumo(insumo_id=insumo.id, cantidad=item.cantidad))
    db.commit()
    return salida(producto)


@router.get("/{producto_id}/lotes", response_model=list[LoteSalida])
def lotes(producto_id: int, db: Db, usuario: Actual) -> list[Lote]:
    obtener(db, producto_id)
    return list(db.scalars(select(Lote).where(Lote.producto_id == producto_id).order_by(Lote.fecha_entrada, Lote.id)))


@router.get("/{producto_id}/kardex", response_model=list[MovimientoSalida])
def kardex(producto_id: int, db: Db, usuario: Actual) -> list[MovimientoSalida]:
    obtener(db, producto_id)
    movs = db.scalars(select(Movimiento).where(Movimiento.producto_id == producto_id).order_by(Movimiento.id))
    return [
        MovimientoSalida(
            id=m.id, tipo=m.tipo, cantidad=m.cantidad, saldo=m.saldo, costo_unitario=m.costo_unitario, usuario_id=m.usuario_id,
            usuario=m.usuario.nombre, fecha=m.fecha, motivo=m.motivo, lote_id=m.lote_id,
        )
        for m in movs
    ]
