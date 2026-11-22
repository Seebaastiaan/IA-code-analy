"""Reglas de la agenda (Requisitos.pdf §3 y §6)."""

from datetime import datetime

import pytest

MIERCOLES_10 = datetime(2026, 12, 2, 10, 0)


# RN-001 · §3.1 y §6.1 (la misma regla, dos veces en el documento) · Un profesional sin citas empalmadas
@pytest.mark.regla("RN-001")
def test_rn001_profesional_no_tiene_citas_empalmadas(crear_cliente, cita, reservar):
    cita(crear_cliente(), MIERCOLES_10)                          # 10:00–11:00
    r = reservar(crear_cliente(), datetime(2026, 12, 2, 10, 30))  # 10:30–11:30, mismo profesional
    assert r.status_code == 409, f"se agendó al profesional en dos citas que se empalman (respuesta {r.status_code})"


@pytest.mark.regla("RN-001")
def test_rn001_profesional_misma_hora(crear_cliente, cita, reservar):
    cita(crear_cliente(), MIERCOLES_10)
    assert reservar(crear_cliente(), MIERCOLES_10).status_code == 409


@pytest.mark.regla("RN-001")
def test_rn001_cita_seguida_si_se_puede(crear_cliente, cita, reservar):
    cita(crear_cliente(), MIERCOLES_10)
    assert reservar(crear_cliente(), datetime(2026, 12, 2, 11, 0)).status_code == 201


# RN-002 · §3.2 · Un cliente sin citas empalmadas
@pytest.mark.regla("RN-002")
def test_rn002_cliente_no_tiene_citas_empalmadas(como, cita, reservar, crear_profesional):
    cita(como("cliente"), MIERCOLES_10)
    r = reservar(como("cliente"), datetime(2026, 12, 2, 10, 30), profesional_=crear_profesional())
    assert r.status_code == 409


# RN-003 · §3.3 · Solo en horario de atención: lunes a sábado, 9:00 a 20:00, la cita completa
@pytest.mark.regla("RN-003")
@pytest.mark.parametrize("inicio", [
    datetime(2026, 12, 6, 10, 0),   # domingo
    datetime(2026, 12, 2, 8, 30),   # antes de abrir
    datetime(2026, 12, 2, 19, 30),  # termina 20:30
])
def test_rn003_fuera_de_horario_se_rechaza(como, reservar, inicio):
    assert reservar(como("cliente"), inicio).status_code == 409


@pytest.mark.regla("RN-003")
@pytest.mark.parametrize("inicio", [datetime(2026, 12, 5, 9, 0), datetime(2026, 12, 2, 19, 0)])  # sábado al abrir · termina 20:00
def test_rn003_dentro_del_horario_se_acepta(como, reservar, inicio):
    assert reservar(como("cliente"), inicio).status_code == 201


# RN-004 · §3.3 · Al menos 2 horas de anticipación (ahora: martes 8:00)
@pytest.mark.regla("RN-004")
def test_rn004_menos_de_dos_horas_se_rechaza(como, reservar):
    assert reservar(como("cliente"), datetime(2026, 12, 1, 9, 30)).status_code == 409


@pytest.mark.regla("RN-004")
def test_rn004_dos_horas_exactas_se_acepta(como, reservar):
    assert reservar(como("cliente"), datetime(2026, 12, 1, 10, 0)).status_code == 201


# RN-005 · §3.4 · Máximo 3 citas activas (duda resuelta: solo futuras y confirmadas)
@pytest.mark.regla("RN-005")
def test_rn005_cuarta_cita_activa_se_rechaza(como, cita, reservar):
    for dia in (2, 3, 4):
        cita(como("cliente"), datetime(2026, 12, dia, 10, 0))
    assert reservar(como("cliente"), datetime(2026, 12, 5, 10, 0)).status_code == 409


@pytest.mark.regla("RN-005")
def test_rn005_canceladas_y_pasadas_no_cuentan(como, cita, reservar, reloj):
    primeras = [cita(como("cliente"), datetime(2026, 12, dia, 10, 0)) for dia in (2, 3, 4)]
    como("cliente").post(f"/citas/{primeras[0]['id']}/cancelar")
    assert reservar(como("cliente"), datetime(2026, 12, 5, 10, 0)).status_code == 201
    reloj.ir_a(datetime(2026, 12, 3, 12, 0))                    # la del día 3 ya pasó
    assert reservar(como("cliente"), datetime(2026, 12, 7, 10, 0)).status_code == 201
