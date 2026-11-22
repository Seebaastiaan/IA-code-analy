"""
Reglas de anticipo y cancelación (Requisitos.pdf §4 y §7).

El documento se contradice: §4.2 reembolsa todo con 24 h y §7.1 cobra 50 % con menos de 48 h; §4.2 reembolsa el
100 % y §7.2 descuenta 10 % de comisión. El equipo resolvió a favor de §4 (referencia/reglas_negocio.toml), y estas
pruebas verifican esa resolución: entre 24 y 48 h el reembolso es total y sin comisión.
"""

from datetime import datetime
from decimal import Decimal

import pytest

JUEVES_10 = datetime(2026, 12, 3, 10, 0)


def cancelar(quien, c):
    r = quien.post(f"/citas/{c['id']}/cancelar")
    assert r.status_code == 200, r.get_data(as_text=True)
    return Decimal(r.get_json()["reembolso"])


# RN-006 · §4.1 · Anticipo del 30 % (duda resuelta: 2 decimales, a la mitad hacia arriba)
@pytest.mark.regla("RN-006")
def test_rn006_anticipo_del_30_por_ciento(cita):
    assert Decimal(cita()["anticipo"]) == Decimal("240.00")


@pytest.mark.regla("RN-006")
def test_rn006_anticipo_redondeado_al_centavo(como, cita):
    s = como("admin").post("/servicios", json={"nombre": "Facial", "duracion_min": 30, "precio": "333.35"}).get_json()
    assert Decimal(cita(servicio_=s)["anticipo"]) == Decimal("100.01")   # 100.005


# RN-007 · §4.2 · Cancelar con 24 h o más: reembolso total
@pytest.mark.regla("RN-007")
def test_rn007_cancelar_con_24_horas_exactas_reembolsa_todo(como, cita, reloj):
    c = cita(inicio=JUEVES_10)
    reloj.ir_a(datetime(2026, 12, 2, 10, 0))
    assert cancelar(como("cliente"), c) == Decimal("240.00"), "«al menos 24 horas» incluye las 24 horas exactas"


@pytest.mark.regla("RN-007")
def test_rn007_entre_24_y_48_horas_reembolsa_todo_sin_comision(como, cita, reloj):
    # Contradicción resuelta: no aplica el 50 % de §7.1 ni la comisión de 10 % de §7.2
    c = cita(inicio=JUEVES_10)
    reloj.ir_a(datetime(2026, 12, 1, 22, 0))                     # 36 h antes
    assert cancelar(como("cliente"), c) == Decimal("240.00")


# RN-008 · §4.3 · Cancelar con menos de 24 h: se retiene el anticipo
@pytest.mark.regla("RN-008")
def test_rn008_menos_de_24_horas_retiene_el_anticipo(como, cita, reloj):
    c = cita(inicio=JUEVES_10)
    reloj.ir_a(datetime(2026, 12, 2, 11, 0))                     # 23 h antes
    assert cancelar(como("cliente"), c) == Decimal("0.00")


@pytest.mark.regla("RN-008")
def test_rn008_cita_que_ya_empezo_no_se_cancela(como, cita, reloj):
    c = cita(inicio=JUEVES_10)
    reloj.ir_a(datetime(2026, 12, 3, 10, 5))
    assert como("cliente").post(f"/citas/{c['id']}/cancelar").status_code == 409


# RN-009 · §4.4 · Premium: reembolso total hasta 12 h antes (excepción, no contradicción)
@pytest.mark.regla("RN-009")
def test_rn009_premium_cancela_gratis_hasta_12_horas(crear_cliente, cita, reloj):
    vip = crear_cliente(premium=True)
    c = cita(vip, JUEVES_10)
    reloj.ir_a(datetime(2026, 12, 2, 21, 0))                     # 13 h antes
    assert cancelar(vip, c) == Decimal("240.00")


@pytest.mark.regla("RN-009")
def test_rn009_premium_con_menos_de_12_horas_retiene(crear_cliente, cita, reloj):
    vip = crear_cliente(premium=True)
    c = cita(vip, JUEVES_10)
    reloj.ir_a(datetime(2026, 12, 2, 23, 0))                     # 11 h antes
    assert cancelar(vip, c) == Decimal("0.00")
