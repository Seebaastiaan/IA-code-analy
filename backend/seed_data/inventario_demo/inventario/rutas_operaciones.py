"""Operaciones que mueven existencias (compras, ventas, mermas, ajustes) y consultas de alertas, bitácora e ingresos."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from inventario.auth import Actual, Db, requiere
from inventario.esquemas import Ajuste, AlertaSalida, AuditoriaSalida, Compra, CompraSalida, Merma, MovimientoSalida, NuevaVenta, VentaSalida
from inventario.modelos import Alerta, Auditoria, Usuario, Venta
from inventario.servicios import activo, ajustar, comprar, merma, salida, vender

router = APIRouter(tags=["operaciones"])

ALMACEN = ("gerente", "almacenista")
CAJA = ("cajero", "barista", "gerente")


@router.post("/compras", status_code=201, response_model=CompraSalida)
def registrar_compra(datos: Compra, db: Db, usuario: Annotated[Usuario, Depends(requiere(*ALMACEN))]) -> CompraSalida:
    producto = activo(db, datos.producto_id)
    lote, mov = comprar(db, producto, datos.cantidad, datos.costo_unitario, usuario, datos.caducidad, datos.fecha_entrada)
    db.commit()
    return CompraSalida(lote_id=lote.id, movimiento_id=mov.id, producto=salida(producto))


@router.post("/ventas", status_code=201, response_model=VentaSalida)
def registrar_venta(datos: NuevaVenta, db: Db, usuario: Annotated[Usuario, Depends(requiere(*CAJA))]) -> VentaSalida:
    lineas = [(activo(db, linea.producto_id), linea.cantidad) for linea in datos.lineas]
    venta = vender(db, lineas, usuario)
    db.commit()
    return VentaSalida(venta_id=venta.id, total=venta.total)


@router.post("/mermas", status_code=201)
def registrar_merma(datos: Merma, db: Db, usuario: Annotated[Usuario, Depends(requiere(*ALMACEN))]) -> dict:
    producto = activo(db, datos.producto_id)
    merma(db, producto, datos.cantidad, datos.motivo, usuario)
    db.commit()
    return {"producto": salida(producto)}


@router.post("/ajustes", status_code=201, response_model=MovimientoSalida)
def registrar_ajuste(datos: Ajuste, db: Db, usuario: Annotated[Usuario, Depends(requiere("gerente"))]) -> MovimientoSalida:
    producto = activo(db, datos.producto_id)
    m = ajustar(db, producto, datos.cantidad, datos.motivo, usuario)
    db.commit()
    return MovimientoSalida(
        id=m.id, tipo=m.tipo, cantidad=m.cantidad, saldo=m.saldo, costo_unitario=m.costo_unitario, usuario_id=m.usuario_id,
        usuario=usuario.nombre, fecha=m.fecha, motivo=m.motivo, lote_id=m.lote_id,
    )


@router.get("/alertas", response_model=list[AlertaSalida])
def alertas(db: Db, usuario: Actual, pendientes: bool = True) -> list[Alerta]:
    consulta = select(Alerta).order_by(Alerta.id)
    if pendientes:
        consulta = consulta.where(Alerta.atendida.is_(False))
    return list(db.scalars(consulta))


@router.get("/auditoria", response_model=list[AuditoriaSalida])
def auditoria(db: Db, usuario: Annotated[Usuario, Depends(requiere("gerente"))], entidad_id: int | None = None) -> list[Auditoria]:
    consulta = select(Auditoria).order_by(Auditoria.id)
    if entidad_id is not None:
        consulta = consulta.where(Auditoria.entidad_id == entidad_id)
    return list(db.scalars(consulta))


@router.get("/ingresos")
def ingresos(db: Db, usuario: Annotated[Usuario, Depends(requiere("gerente"))]) -> dict:
    total = db.scalars(select(Venta.total)).all()
    return {"ventas": db.scalar(select(func.count()).select_from(Venta)), "total": str(sum(total, Decimal(0)))}
