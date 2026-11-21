"""Reglas del catálogo de productos (Requerimientos.docx §4)."""

from decimal import Decimal

import pytest


# RN-001 · §4.3 · Un producto con historial no se borra: pasa a Inactivo
@pytest.mark.regla("RN-001")
def test_rn001_producto_con_historial_queda_inactivo(como, crear_producto):
    p = crear_producto(stock_actual=5)                                 # la compra deja un movimiento en el Kardex
    como("gerente").delete(f"/productos/{p['id']}")
    r = como("gerente").get(f"/productos/{p['id']}")
    assert r.status_code == 200, "el producto con historial se borró físicamente"
    assert r.json()["estado"] == "inactivo"
    assert len(como("gerente").get(f"/productos/{p['id']}/kardex").json()) == 1, "se perdió el historial del producto"


@pytest.mark.regla("RN-001")
def test_rn001_producto_sin_historial_si_se_borra(como, crear_producto):
    # Duda resuelta: sin movimientos, el borrado físico está permitido
    p = crear_producto()
    assert como("gerente").delete(f"/productos/{p['id']}").status_code == 204
    assert como("gerente").get(f"/productos/{p['id']}").status_code == 404


# RN-002, RN-003, RN-004 · §4.2 · Unicidad
@pytest.mark.regla("RN-002")
def test_rn002_sku_unico(como, crear_producto):
    crear_producto(sku="CAF-001")
    r = como("gerente").post("/productos", json={"sku": "CAF-001", "codigo_barras": "999", "nombre_interno": "Otro", "precio_base": "10"})
    assert r.status_code == 409
    assert len(como("gerente").get("/productos").json()) == 1


@pytest.mark.regla("RN-003")
def test_rn003_codigo_de_barras_unico(como, crear_producto):
    crear_producto(codigo_barras="7501234567890")
    r = como("gerente").post("/productos", json={"sku": "X-1", "codigo_barras": "7501234567890", "nombre_interno": "Otro", "precio_base": "10"})
    assert r.status_code == 409
    assert len(como("gerente").get("/productos").json()) == 1


@pytest.mark.regla("RN-004")
def test_rn004_nombre_interno_unico_sin_distinguir_mayusculas(como, crear_producto):
    # Duda resuelta: se comparan sin mayúsculas y sin espacios repetidos
    crear_producto(nombre_interno="Café Molido Americano")
    r = como("gerente").post("/productos", json={"sku": "X-2", "codigo_barras": "888", "nombre_interno": "  café  molido americano ", "precio_base": "10"})
    assert r.status_code == 409


@pytest.mark.regla("RN-004")
def test_rn004_no_se_renombra_a_un_nombre_existente(como, crear_producto):
    crear_producto(nombre_interno="Leche entera")
    otro = crear_producto(nombre_interno="Leche deslactosada")
    r = como("gerente").patch(f"/productos/{otro['id']}", json={"nombre_interno": "LECHE ENTERA"})
    assert r.status_code == 409


# RN-005 · §4.4 · Unidad base bloqueada con movimientos
@pytest.mark.regla("RN-005")
def test_rn005_unidad_base_no_cambia_con_movimientos(como, crear_producto):
    p = crear_producto(stock_actual=1000, unidad_base="g", tipo="insumo")
    r = como("gerente").patch(f"/productos/{p['id']}", json={"unidad_base": "ml"})
    assert r.status_code == 409
    assert como("gerente").get(f"/productos/{p['id']}").json()["unidad_base"] == "g"


@pytest.mark.regla("RN-005")
def test_rn005_unidad_base_cambia_sin_movimientos(como, crear_producto):
    p = crear_producto(unidad_base="g", tipo="insumo")
    r = como("gerente").patch(f"/productos/{p['id']}", json={"unidad_base": "ml"})
    assert r.status_code == 200
    assert r.json()["unidad_base"] == "ml"


# RN-013 · §4.5 · Precio de venta mayor a cero
@pytest.mark.regla("RN-013")
@pytest.mark.parametrize("precio", ["0", "-5"])
def test_rn013_precio_de_venta_mayor_a_cero(como, precio):
    r = como("gerente").post("/productos", json={"sku": "X-3", "codigo_barras": "777", "nombre_interno": "Galleta", "precio_base": precio})
    assert r.status_code == 422
    assert como("gerente").get("/productos").json() == []


@pytest.mark.regla("RN-013")
def test_rn013_no_se_edita_a_precio_cero(como, crear_producto):
    p = crear_producto(precio_base="20")
    assert como("gerente").patch(f"/productos/{p['id']}", json={"precio_base": "0"}).status_code == 422
    assert Decimal(como("gerente").get(f"/productos/{p['id']}").json()["precio_base"]) == Decimal("20")


# RN-014 · §4.5 · Precio menor al costo: se permite con aviso (duda resuelta)
@pytest.mark.regla("RN-014")
def test_rn014_precio_menor_al_costo_se_avisa(como, crear_producto):
    r = como("gerente").post("/productos", json={
        "sku": "X-4", "codigo_barras": "666", "nombre_interno": "Pan dulce", "precio_base": "10", "costo_unitario": "12",
    })
    assert r.status_code == 201, "el precio menor al costo se bloqueó; la regla dice que solo se avisa"
    assert "precio_menor_al_costo" in r.json()["avisos"]


@pytest.mark.regla("RN-014")
def test_rn014_sin_aviso_si_el_precio_cubre_el_costo(crear_producto):
    p = crear_producto(precio_base="15", costo_unitario="12")
    assert p["avisos"] == []


# RN-016 · §4.6 · Precio base e impuestos separados
@pytest.mark.regla("RN-016")
def test_rn016_precio_base_e_impuestos_por_separado(crear_producto):
    p = crear_producto(precio_base="100", iva_tasa="0.16", ieps_tasa="0.08")
    assert Decimal(p["precio_base"]) == Decimal("100"), "el precio base incluye impuestos"
    imp = p["impuestos"]
    assert Decimal(imp["iva_tasa"]) == Decimal("0.16") and Decimal(imp["ieps_tasa"]) == Decimal("0.08")
    assert Decimal(imp["iva"]) > 0 and Decimal(imp["ieps"]) > 0
    assert Decimal(p["precio_con_impuestos"]) == Decimal(p["precio_base"]) + Decimal(imp["iva"]) + Decimal(imp["ieps"])


@pytest.mark.regla("RN-016")
def test_rn016_cambiar_impuestos_no_cambia_el_precio_base(como, crear_producto):
    p = crear_producto(precio_base="100", iva_tasa="0.16")
    r = como("gerente").patch(f"/productos/{p['id']}", json={"iva_tasa": "0"})
    assert Decimal(r.json()["precio_base"]) == Decimal("100")
    assert Decimal(r.json()["precio_con_impuestos"]) == Decimal("100")
