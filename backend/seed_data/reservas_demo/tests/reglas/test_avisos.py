"""Reglas de avisos por correo (Requisitos.pdf §5). `buzon` guarda lo que la app envió."""

from datetime import datetime

import pytest

JUEVES_10 = datetime(2026, 12, 3, 10, 0)


# RN-010 · §5.1 · Correo de confirmación con folio, servicio, fecha y hora
@pytest.mark.regla("RN-010")
def test_rn010_correo_de_confirmacion(como, cita, buzon):
    c = cita(inicio=JUEVES_10)
    assert len(buzon) == 1
    m = buzon[0]
    assert m["para"] == como("cliente").usuario["email"]
    assert c["folio"] in m["asunto"] + m["cuerpo"]
    assert "Masaje relajante" in m["cuerpo"] and "03/12/2026" in m["cuerpo"] and "10:00" in m["cuerpo"]


@pytest.mark.regla("RN-010")
def test_rn010_sin_correo_si_la_reserva_se_rechaza(como, reservar, buzon):
    assert reservar(como("cliente"), datetime(2026, 12, 6, 10, 0)).status_code == 409   # domingo
    assert buzon == []


# RN-011 · §5.2 · Correo de cancelación con el monto reembolsado
@pytest.mark.regla("RN-011")
def test_rn011_correo_de_cancelacion_con_reembolso(como, cita, buzon):
    c = cita(inicio=JUEVES_10)
    como("cliente").post(f"/citas/{c['id']}/cancelar")
    m = buzon[-1]
    assert m["para"] == como("cliente").usuario["email"] and c["folio"] in m["asunto"] + m["cuerpo"]
    assert "$240.00" in m["cuerpo"]


# RN-012 · §5.3 · Recordatorio una sola vez, 24 h antes (duda resuelta: dentro de las 24 h previas)
@pytest.mark.regla("RN-012")
def test_rn012_recordatorio_una_vez_dentro_de_las_24_horas(como, cita, buzon, reloj):
    c = cita(inicio=JUEVES_10)
    buzon.clear()
    reloj.ir_a(datetime(2026, 12, 2, 9, 0))                      # faltan 25 h
    assert como("recepcion").post("/tareas/recordatorios").get_json()["enviados"] == 0
    reloj.ir_a(datetime(2026, 12, 2, 11, 0))                     # faltan 23 h
    assert como("recepcion").post("/tareas/recordatorios").get_json()["enviados"] == 1
    assert len(buzon) == 1 and c["folio"] in buzon[0]["asunto"] + buzon[0]["cuerpo"]
    reloj.avanzar(hours=1)
    assert como("recepcion").post("/tareas/recordatorios").get_json()["enviados"] == 0, "el recordatorio se mandó dos veces"


@pytest.mark.regla("RN-012")
def test_rn012_cita_cancelada_no_recibe_recordatorio(como, cita, buzon, reloj):
    c = cita(inicio=JUEVES_10)
    como("cliente").post(f"/citas/{c['id']}/cancelar")
    reloj.ir_a(datetime(2026, 12, 2, 11, 0))
    assert como("recepcion").post("/tareas/recordatorios").get_json()["enviados"] == 0
