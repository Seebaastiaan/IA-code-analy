"""RN-018 · §8.2 · Bitácora de cambios de precio, costo y ajustes manuales."""

from decimal import Decimal

import pytest


def bitacora(como, producto, campo):
    return [a for a in como("gerente").get("/auditoria", params={"entidad_id": producto["id"]}).json() if a["campo"] == campo]


@pytest.mark.regla("RN-018")
def test_rn018_cambio_de_precio_queda_en_bitacora(como, crear_producto, usuario_id):
    p = crear_producto(precio_base="20")
    assert como("gerente").patch(f"/productos/{p['id']}", json={"precio_base": "25"}).status_code == 200
    registros = bitacora(como, p, "precio_base")
    assert len(registros) == 1
    r = registros[0]
    assert r["usuario_id"] == usuario_id("gerente") and r["fecha"]
    assert Decimal(r["valor_anterior"]) == Decimal("20"), f"valor anterior {r['valor_anterior']}, debía ser 20"
    assert Decimal(r["valor_nuevo"]) == Decimal("25")


@pytest.mark.regla("RN-018")
def test_rn018_cambio_de_costo_queda_en_bitacora(como, crear_producto):
    p = crear_producto(costo_unitario="8")
    como("gerente").patch(f"/productos/{p['id']}", json={"costo_unitario": "9.50"})
    r = bitacora(como, p, "costo_unitario")
    assert len(r) == 1
    assert (Decimal(r[0]["valor_anterior"]), Decimal(r[0]["valor_nuevo"])) == (Decimal("8"), Decimal("9.50"))


@pytest.mark.regla("RN-018")
def test_rn018_ajuste_manual_queda_en_bitacora(como, crear_producto, usuario_id):
    p = crear_producto(stock_actual=10)
    assert como("gerente").post("/ajustes", json={"producto_id": p["id"], "cantidad": "-2", "motivo": "conteo físico"}).status_code == 201
    r = bitacora(como, p, "stock_actual")
    assert len(r) == 1
    assert (Decimal(r[0]["valor_anterior"]), Decimal(r[0]["valor_nuevo"])) == (Decimal(10), Decimal(8))
    assert r[0]["usuario_id"] == usuario_id("gerente")
