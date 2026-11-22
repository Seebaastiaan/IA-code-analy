"""Reglas de existencias, Kardex, lotes y mermas (Requerimientos.docx §5)."""

from datetime import date, datetime
from decimal import Decimal

import pytest


def stock(como, producto) -> Decimal:
    return Decimal(como("gerente").get(f"/productos/{producto['id']}").json()["stock_actual"])


# RN-006 · §5.1 · El stock nunca es negativo
@pytest.mark.regla("RN-006")
def test_rn006_no_se_vende_sin_existencias(como, crear_producto, vender):
    p = crear_producto(stock_actual=3)
    r = vender(p, 5)
    assert r.status_code == 409, f"se vendieron 5 con 3 en existencia (respuesta {r.status_code})"
    assert stock(como, p) == 3


@pytest.mark.regla("RN-006")
def test_rn006_merma_no_deja_stock_negativo(como, crear_producto):
    p = crear_producto(stock_actual=2)
    r = como("almacenista").post("/mermas", json={"producto_id": p["id"], "cantidad": "5", "motivo": "caducado"})
    assert r.status_code == 409
    assert stock(como, p) == 2


@pytest.mark.regla("RN-006")
def test_rn006_ajuste_no_deja_stock_negativo(como, crear_producto):
    p = crear_producto(stock_actual=2)
    r = como("gerente").post("/ajustes", json={"producto_id": p["id"], "cantidad": "-3", "motivo": "conteo"})
    assert r.status_code == 409
    assert stock(como, p) == 2


# RN-007 · §5.2 · El stock solo cambia con un movimiento del Kardex
@pytest.mark.regla("RN-007")
def test_rn007_stock_no_se_edita_directo(como, crear_producto):
    p = crear_producto(stock_actual=10)
    como("gerente").patch(f"/productos/{p['id']}", json={"stock_actual": "999"})
    assert stock(como, p) == 10, "stock_actual cambió sin un movimiento"


@pytest.mark.regla("RN-007")
def test_rn007_cada_cambio_de_stock_deja_movimiento(como, crear_producto, comprar, usuario_id):
    p = crear_producto(stock_actual=10)
    comprar(p, 5)
    kardex = como("gerente").get(f"/productos/{p['id']}/kardex").json()
    ultimo = kardex[-1]
    assert ultimo["tipo"] == "entrada" and Decimal(ultimo["cantidad"]) == 5 and Decimal(ultimo["saldo"]) == 15
    assert ultimo["usuario_id"] == usuario_id("almacenista") and ultimo["fecha"]
    assert stock(como, p) == sum(Decimal(m["cantidad"]) for m in kardex), "el stock no coincide con la suma del Kardex"


# RN-008 · §5.4 · PEPS por fecha de entrada (duda resuelta: no por caducidad)
@pytest.mark.regla("RN-008")
def test_rn008_la_venta_sale_del_lote_mas_antiguo(como, crear_producto, comprar, vender):
    p = crear_producto()
    a = comprar(p, 5, fecha_entrada=datetime(2026, 1, 10), caducidad=date(2026, 12, 31))
    b = comprar(p, 5, fecha_entrada=datetime(2026, 2, 10), caducidad=date(2026, 6, 30))   # caduca antes, pero entró después
    assert vender(p, 3).status_code == 201
    lotes = {lote["id"]: Decimal(lote["cantidad_disponible"]) for lote in como("gerente").get(f"/productos/{p['id']}/lotes").json()}
    assert lotes[a["lote_id"]] == 2 and lotes[b["lote_id"]] == 5


@pytest.mark.regla("RN-008")
def test_rn008_al_agotar_un_lote_sigue_el_siguiente(como, crear_producto, comprar, vender):
    p = crear_producto()
    a = comprar(p, 2, fecha_entrada=datetime(2026, 1, 10))
    b = comprar(p, 5, fecha_entrada=datetime(2026, 2, 10))
    assert vender(p, 4).status_code == 201
    lotes = {lote["id"]: Decimal(lote["cantidad_disponible"]) for lote in como("gerente").get(f"/productos/{p['id']}/lotes").json()}
    assert lotes[a["lote_id"]] == 0 and lotes[b["lote_id"]] == 3


# RN-009 · §5.5 · Alerta al llegar al stock mínimo (duda resuelta: con ≤)
@pytest.mark.regla("RN-009")
def test_rn009_alerta_al_llegar_al_minimo(como, crear_producto, vender):
    p = crear_producto(stock_actual=10, stock_minimo=5)
    assert vender(p, 5).status_code == 201
    producto = como("gerente").get(f"/productos/{p['id']}").json()
    assert producto["requiere_reabastecer"] is True
    alertas = [a for a in como("gerente").get("/alertas").json() if a["producto_id"] == p["id"]]
    assert len(alertas) == 1 and alertas[0]["tipo"] == "stock_minimo"


@pytest.mark.regla("RN-009")
def test_rn009_sin_alerta_arriba_del_minimo(como, crear_producto, vender):
    p = crear_producto(stock_actual=10, stock_minimo=5)
    assert vender(p, 4).status_code == 201
    assert como("gerente").get(f"/productos/{p['id']}").json()["requiere_reabastecer"] is False
    assert [a for a in como("gerente").get("/alertas").json() if a["producto_id"] == p["id"]] == []


# RN-011 · §6.2 · Conversión de unidades de compra a unidades base
@pytest.mark.regla("RN-011")
def test_rn011_compra_por_costal_suma_gramos(como, crear_producto, comprar):
    cafe = crear_producto(tipo="insumo", unidad_base="g", unidad_compra="costal", factor_compra="1000")
    comprar(cafe, 2, costo="500")
    assert stock(como, cafe) == 2000
    assert Decimal(como("gerente").get(f"/productos/{cafe['id']}").json()["costo_unitario"]) == Decimal("0.50")


# RN-012 · §5.6 · Mermas: descuentan stock sin sumar ingresos
@pytest.mark.regla("RN-012")
def test_rn012_merma_descuenta_sin_ingreso(como, crear_producto):
    p = crear_producto(stock_actual=10)
    antes = como("gerente").get("/ingresos").json()
    r = como("almacenista").post("/mermas", json={"producto_id": p["id"], "cantidad": "2", "motivo": "se cayó"})
    assert r.status_code == 201
    assert stock(como, p) == 8
    assert como("gerente").get("/ingresos").json() == antes, "la merma generó un ingreso"
    assert como("gerente").get(f"/productos/{p['id']}/kardex").json()[-1]["tipo"] == "merma"
