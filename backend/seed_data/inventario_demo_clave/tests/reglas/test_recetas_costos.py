"""Reglas de recetas y costos (Requerimientos.docx §6 y §7)."""

from decimal import Decimal

import pytest


# RN-010 · §6.1 · Un producto con receta descuenta sus insumos en proporción
@pytest.mark.regla("RN-010")
def test_rn010_venta_con_receta_descuenta_insumos(como, crear_producto, vender):
    leche = crear_producto(tipo="insumo", unidad_base="ml", stock_actual=1000)
    cafe = crear_producto(tipo="insumo", unidad_base="g", stock_actual=500)
    latte = crear_producto(tipo="compuesto", precio_base="55")
    r = como("gerente").put(f"/productos/{latte['id']}/receta", json={"insumos": [
        {"insumo_id": leche["id"], "cantidad": "200"}, {"insumo_id": cafe["id"], "cantidad": "18"},
    ]})
    assert r.status_code == 200
    assert vender(latte, 2, rol="barista").status_code == 201
    assert Decimal(como("gerente").get(f"/productos/{leche['id']}").json()["stock_actual"]) == 600
    assert Decimal(como("gerente").get(f"/productos/{cafe['id']}").json()["stock_actual"]) == 464


@pytest.mark.regla("RN-010")
def test_rn010_producto_de_reventa_descuenta_uno_a_uno(como, crear_producto, vender):
    agua = crear_producto(stock_actual=12)
    assert vender(agua, 3).status_code == 201
    assert Decimal(como("gerente").get(f"/productos/{agua['id']}").json()["stock_actual"]) == 9


# RN-015 · §7.1 · Costo promedio ponderado (duda resuelta: 2 decimales, redondeo a la mitad hacia arriba)
@pytest.mark.regla("RN-015")
def test_rn015_costo_promedio_ponderado(como, crear_producto, comprar):
    p = crear_producto()
    comprar(p, 10, costo="10")
    comprar(p, 30, costo="20")
    costo = Decimal(como("gerente").get(f"/productos/{p['id']}").json()["costo_unitario"])
    assert costo == Decimal("17.50"), f"costo promedio {costo}; con 10 u a $10 y 30 u a $20 debe ser $17.50"


@pytest.mark.regla("RN-015")
def test_rn015_primera_compra_fija_el_costo(como, crear_producto, comprar):
    p = crear_producto()
    comprar(p, 4, costo="12.345")
    assert Decimal(como("gerente").get(f"/productos/{p['id']}").json()["costo_unitario"]) == Decimal("12.35")
