from pagos.procesador import procesar


def test_rechaza_sin_monto():
    r = procesar([{"id": 1}], {}, 0, 1000)
    assert r["rechazados"][0]["motivo"] == "sin monto"


def test_cobra_pago_valido():
    r = procesar([{"id": 2, "monto": 100, "moneda": "MXN"}], {}, 0, 1000)
    assert r["ok"][0]["estado"] == "cobrado"
