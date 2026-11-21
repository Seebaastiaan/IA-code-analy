"""Lógica del inventario: Kardex, lotes PEPS, compras, ventas, mermas, ajustes y bitácora."""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from inventario.esquemas import Impuestos, ProductoSalida
from inventario.modelos import Alerta, Auditoria, Lote, Movimiento, Producto, Usuario, Venta, VentaLinea, ahora

CENTAVO = Decimal("0.01")
CERO = Decimal(0)


def dinero(valor: Decimal) -> Decimal:
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def normalizar_nombre(nombre: str) -> str:
    return " ".join(nombre.split()).casefold()


def obtener(db: Session, producto_id: int) -> Producto:
    producto = db.get(Producto, producto_id)
    if producto is None:
        raise HTTPException(404, "No existe el producto")
    return producto


def activo(db: Session, producto_id: int) -> Producto:
    producto = obtener(db, producto_id)
    if producto.estado != "activo":
        raise HTTPException(409, "El producto está inactivo")
    return producto


def tiene_movimientos(db: Session, producto: Producto) -> bool:
    return db.scalar(select(func.count()).select_from(Movimiento).where(Movimiento.producto_id == producto.id)) > 0


def salida(producto: Producto) -> ProductoSalida:
    base = producto.precio_base
    ieps = dinero(base * producto.ieps_tasa)
    iva = dinero((base + ieps) * producto.iva_tasa)
    avisos = ["precio_menor_al_costo"] if base < producto.costo_unitario else []
    return ProductoSalida(
        id=producto.id, sku=producto.sku, codigo_barras=producto.codigo_barras, nombre_interno=producto.nombre_interno,
        tipo=producto.tipo, unidad_base=producto.unidad_base, unidad_compra=producto.unidad_compra,
        factor_compra=producto.factor_compra, precio_base=base,
        impuestos=Impuestos(iva_tasa=producto.iva_tasa, ieps_tasa=producto.ieps_tasa, ieps=ieps, iva=iva),
        precio_con_impuestos=base + ieps + iva, costo_unitario=producto.costo_unitario,
        stock_actual=producto.stock_actual, stock_minimo=producto.stock_minimo, estado=producto.estado,
        requiere_reabastecer=producto.requiere_reabastecer, avisos=avisos,
    )


# ───────────────────────── Bitácora ─────────────────────────


def auditar(db: Session, usuario: Usuario, entidad: str, entidad_id: int, campo: str, anterior: object, nuevo: object) -> None:
    db.add(Auditoria(
        entidad=entidad, entidad_id=entidad_id, campo=campo, usuario_id=usuario.id,
        valor_anterior=None if anterior is None else str(anterior), valor_nuevo=None if nuevo is None else str(nuevo),
    ))


# ───────────────────────── Kardex ─────────────────────────


def _revisar_minimo(db: Session, producto: Producto) -> None:
    if producto.stock_actual <= producto.stock_minimo:
        if not producto.requiere_reabastecer:
            producto.requiere_reabastecer = True
            db.add(Alerta(
                producto_id=producto.id, tipo="stock_minimo",
                mensaje=f"{producto.nombre_interno}: quedan {producto.stock_actual} {producto.unidad_base} (mínimo {producto.stock_minimo})",
            ))
    else:
        producto.requiere_reabastecer = False


def movimiento(
    db: Session, producto: Producto, tipo: str, cantidad: Decimal, usuario: Usuario, *,
    costo: Decimal | None = None, motivo: str | None = None, lote: Lote | None = None, venta: Venta | None = None,
) -> Movimiento:
    """Único lugar donde cambian las existencias: actualiza el stock y deja el renglón del Kardex."""
    producto.stock_actual = producto.stock_actual + cantidad
    mov = Movimiento(
        producto_id=producto.id, tipo=tipo, cantidad=cantidad, saldo=producto.stock_actual,
        costo_unitario=producto.costo_unitario if costo is None else costo, usuario_id=usuario.id, motivo=motivo,
        lote_id=lote.id if lote else None, venta_id=venta.id if venta else None,
    )
    db.add(mov)
    _revisar_minimo(db, producto)
    return mov


def descontar(db: Session, producto: Producto, cantidad: Decimal, tipo: str, usuario: Usuario, *, motivo: str | None = None, venta: Venta | None = None) -> None:
    """Saca existencias de los lotes en orden PEPS: primero el lote que entró primero."""
    # Las cantidades se guardan como texto: se filtran aquí, no en SQL
    lotes = db.scalars(select(Lote).where(Lote.producto_id == producto.id).order_by(Lote.fecha_entrada, Lote.id)).all()
    pendiente = cantidad
    for lote in lotes:
        if pendiente <= 0:
            break
        if lote.cantidad_disponible <= 0:
            continue
        toma = min(lote.cantidad_disponible, pendiente)
        lote.cantidad_disponible = lote.cantidad_disponible - toma
        movimiento(db, producto, tipo, -toma, usuario, costo=lote.costo_unitario, motivo=motivo, lote=lote, venta=venta)
        pendiente -= toma
    if pendiente > 0:
        movimiento(db, producto, tipo, -pendiente, usuario, motivo=motivo, venta=venta)


# ───────────────────────── Operaciones ─────────────────────────


def comprar(
    db: Session, producto: Producto, cantidad: Decimal, costo_compra: Decimal, usuario: Usuario, caducidad=None, fecha_entrada: datetime | None = None,
) -> tuple[Lote, Movimiento]:
    if producto.tipo == "compuesto":
        raise HTTPException(409, "Un producto con receta no se compra: se compran sus insumos")
    unidades = cantidad * producto.factor_compra
    costo_base = costo_compra / producto.factor_compra
    if producto.stock_actual > 0:
        producto.costo_unitario = dinero((producto.costo_unitario + costo_base) / 2)
    else:
        producto.costo_unitario = dinero(costo_base)
    lote = Lote(
        producto_id=producto.id, caducidad=caducidad, cantidad_inicial=unidades, cantidad_disponible=unidades, costo_unitario=costo_base,
        fecha_entrada=fecha_entrada.replace(tzinfo=None) if fecha_entrada else ahora(),
    )
    db.add(lote)
    db.flush()
    mov = movimiento(db, producto, "entrada", unidades, usuario, costo=costo_base, lote=lote, motivo="compra")
    return lote, mov


def vender(db: Session, lineas: list[tuple[Producto, Decimal]], usuario: Usuario) -> Venta:
    venta = Venta(usuario_id=usuario.id, total=CERO)
    db.add(venta)
    db.flush()
    total = CERO
    for producto, cantidad in lineas:
        if producto.tipo == "compuesto":
            if not producto.receta:
                raise HTTPException(409, f"{producto.nombre_interno} no tiene receta")
            for item in producto.receta:
                necesario = item.cantidad * cantidad
                if item.insumo.stock_actual < necesario:
                    raise HTTPException(409, f"No alcanza {item.insumo.nombre_interno} para {producto.nombre_interno}")
                descontar(db, item.insumo, necesario, "consumo_receta", usuario, venta=venta)
        else:
            descontar(db, producto, cantidad, "venta", usuario, venta=venta)
        precio = salida(producto).precio_con_impuestos
        importe = dinero(precio * cantidad)
        db.add(VentaLinea(venta_id=venta.id, producto_id=producto.id, cantidad=cantidad, precio_unitario=precio, importe=importe))
        total += importe
    venta.total = total
    return venta


def merma(db: Session, producto: Producto, cantidad: Decimal, motivo: str, usuario: Usuario) -> None:
    """Producto que se tira o se echa a perder: sale del stock y no genera ingreso."""
    if cantidad > producto.stock_actual:
        raise HTTPException(409, f"Solo hay {producto.stock_actual} {producto.unidad_base}")
    descontar(db, producto, cantidad, "merma", usuario, motivo=motivo)


def ajustar(db: Session, producto: Producto, cantidad: Decimal, motivo: str, usuario: Usuario) -> Movimiento:
    """Ajuste manual tras un conteo físico."""
    if cantidad == 0:
        raise HTTPException(422, "El ajuste no puede ser 0")
    anterior = producto.stock_actual
    if anterior + cantidad < 0:
        raise HTTPException(409, "El ajuste dejaría el stock negativo")
    if cantidad < 0:
        descontar(db, producto, -cantidad, "ajuste", usuario, motivo=motivo)
        mov = None
    else:
        mov = movimiento(db, producto, "ajuste", cantidad, usuario, motivo=motivo)
    auditar(db, usuario, "producto", producto.id, "stock_actual", anterior, producto.stock_actual)
    db.flush()
    return mov or db.scalars(select(Movimiento).where(Movimiento.producto_id == producto.id).order_by(Movimiento.id.desc())).first()
