"""
RN-017 · §8.1 · Permisos por rol.

El documento solo dice «cajeros y baristas venden; gerentes y almacenistas administran el inventario». La matriz
completa la resolvió el equipo (referencia/reglas_negocio.toml) y es la que se prueba aquí: cada celda es una prueba.
"""

import pytest

ROLES = ("cajero", "barista", "gerente", "almacenista")

# acción: (método, ruta, cuerpo, roles permitidos)
MATRIZ = {
    "crear producto": ("post", "/productos", lambda p: {"sku": "N-1", "codigo_barras": "N-1", "nombre_interno": "Nuevo", "precio_base": "5"},
                       {"gerente", "almacenista"}),
    "editar catálogo": ("patch", "/productos/{id}", lambda p: {"nombre_interno": "Renombrado"}, {"gerente", "almacenista"}),
    "cambiar precio": ("patch", "/productos/{id}", lambda p: {"precio_base": "99"}, {"gerente"}),
    "cambiar costo": ("patch", "/productos/{id}", lambda p: {"costo_unitario": "7"}, {"gerente"}),
    "eliminar producto": ("delete", "/productos/{id}", None, {"gerente"}),
    "registrar compra": ("post", "/compras", lambda p: {"producto_id": p["id"], "cantidad": "1", "costo_unitario": "10"}, {"gerente", "almacenista"}),
    "vender": ("post", "/ventas", lambda p: {"lineas": [{"producto_id": p["id"], "cantidad": "1"}]}, {"cajero", "barista", "gerente"}),
    "registrar merma": ("post", "/mermas", lambda p: {"producto_id": p["id"], "cantidad": "1", "motivo": "rota"}, {"gerente", "almacenista"}),
    "ajuste manual": ("post", "/ajustes", lambda p: {"producto_id": p["id"], "cantidad": "1", "motivo": "conteo"}, {"gerente"}),
    "ver bitácora": ("get", "/auditoria", None, {"gerente"}),
    "ver ingresos": ("get", "/ingresos", None, {"gerente"}),
}

CASOS = [(accion, rol) for accion in MATRIZ for rol in ROLES]


@pytest.mark.regla("RN-017")
@pytest.mark.parametrize(("accion", "rol"), CASOS, ids=[f"{a}-{r}" for a, r in CASOS])
def test_rn017_matriz_de_permisos(como, crear_producto, accion, rol):
    metodo, ruta, cuerpo, permitidos = MATRIZ[accion]
    p = crear_producto(stock_actual=10)
    kwargs = {"json": cuerpo(p)} if cuerpo else {}
    r = getattr(como(rol), metodo)(ruta.format(id=p["id"]), **kwargs)
    if rol in permitidos:
        assert r.status_code != 403, f"{rol} debería poder «{accion}»"
    else:
        assert r.status_code == 403, f"{rol} no debería poder «{accion}» (respuesta {r.status_code})"
