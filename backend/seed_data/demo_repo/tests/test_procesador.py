from pagos.procesador import procesar


def test_rechaza_sin_monto():
    r = procesar([{"id": 1}], {}, 0, 1000)
    assert r["rechazados"][0]["motivo"] == "sin monto"


def test_cobra_pago_valido():
    r = procesar([{"id": 2, "monto": 100, "moneda": "MXN"}], {}, 0, 1000)
    assert r["ok"][0]["estado"] == "cobrado"


# Regla de negocio RN-004 (reglas_negocio.toml): el nombre test_rn004_… la liga sin marcador
def test_rn004_pago_sobre_el_limite_requiere_autorizador_valido():
    pago = {"id": 3, "monto": 5000, "moneda": "MXN", "autorizado": True, "autorizado_por": "ventas"}
    r = procesar([pago], {}, 0, 1000)
    assert r["rechazados"] == [{"id": 3, "motivo": "autorizador"}]
