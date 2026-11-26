"""
Datos de ejemplo para probar la interfaz (opcional):

    python -m inventario.datos_demo

Crea un catálogo pequeño de cafetería con compras, una receta y una merma, usando las mismas funciones que la API. No
hace nada si ya hay productos.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from inventario.db import SessionLocal
from inventario.esquemas import InsumoReceta, ProductoNuevo, Receta
from inventario.main import preparar_base
from inventario.modelos import Producto, Usuario
from inventario.rutas_productos import crear, definir_receta
from inventario.servicios import comprar, merma


def sembrar() -> str:
    preparar_base()
    with SessionLocal() as db:
        if db.scalar(select(Producto.id)) is not None:
            return "Ya hay productos: no se agregó nada."
        gerente = db.scalar(select(Usuario).where(Usuario.rol == "gerente"))

        def producto(**datos) -> Producto:
            salida = crear(ProductoNuevo(**datos), db, gerente)
            return db.get(Producto, salida.id)

        cafe = producto(sku="CAF-001", codigo_barras="7501000000011", nombre_interno="Café en grano", tipo="insumo", unidad_base="g",
                        unidad_compra="costal 1 kg", factor_compra=1000, precio_base=1, stock_minimo=500)
        leche = producto(sku="LEC-001", codigo_barras="7501000000028", nombre_interno="Leche entera", tipo="insumo", unidad_base="ml",
                         unidad_compra="caja 12 L", factor_compra=12000, precio_base=1, stock_minimo=3000)
        galleta = producto(sku="GAL-001", codigo_barras="7501000000035", nombre_interno="Galleta de avena", tipo="reventa",
                           unidad_compra="caja 24 pzas", factor_compra=24, precio_base=25, costo_unitario=10, stock_minimo=10)
        latte = producto(sku="LAT-001", codigo_barras="7501000000042", nombre_interno="Latte", tipo="compuesto", precio_base=55)

        hoy = datetime.now()
        # Dos compras del café a distinto costo (el costo promedio queda a la vista) y una de leche que caduca pronto
        comprar(db, cafe, Decimal(2), Decimal(380), gerente, fecha_entrada=hoy - timedelta(days=10))
        comprar(db, cafe, Decimal(1), Decimal(420), gerente, fecha_entrada=hoy - timedelta(days=2))
        comprar(db, leche, Decimal(1), Decimal(264), gerente, caducidad=date.today() + timedelta(days=5))
        comprar(db, galleta, Decimal(2), Decimal(240), gerente)
        db.commit()
        definir_receta(latte.id, Receta(insumos=[InsumoReceta(insumo_id=cafe.id, cantidad=Decimal(18))]), db, gerente)
        merma(db, galleta, Decimal(3), "Se cayeron al piso", gerente)
        db.commit()
        return "Listo: 4 productos con compras, una receta y una merma."


if __name__ == "__main__":
    print(sembrar())
