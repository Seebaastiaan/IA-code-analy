"""Reglas de privacidad, acceso y permisos (Requisitos.pdf §8)."""

from datetime import datetime

import pytest


# RN-013 · §8.1 · Un cliente solo ve y cancela sus propias citas
@pytest.mark.regla("RN-013")
def test_rn013_un_cliente_no_ve_la_cita_de_otro(crear_cliente, cita):
    ana, beto = crear_cliente(), crear_cliente()
    c = cita(ana)
    r = beto.get(f"/citas/{c['id']}")
    assert r.status_code == 404, f"un cliente vio la cita de otro (respuesta {r.status_code})"


@pytest.mark.regla("RN-013")
def test_rn013_un_cliente_no_cancela_la_cita_de_otro(crear_cliente, cita, como):
    ana, beto = crear_cliente(), crear_cliente()
    c = cita(ana)
    assert beto.post(f"/citas/{c['id']}/cancelar").status_code == 404
    assert ana.get(f"/citas/{c['id']}").get_json()["estado"] == "confirmada"


@pytest.mark.regla("RN-013")
def test_rn013_la_lista_solo_trae_las_propias(crear_cliente, cita):
    ana, beto = crear_cliente(), crear_cliente()
    cita(ana)
    cita(beto, datetime(2026, 12, 3, 12, 0))
    assert {c["cliente_id"] for c in beto.get("/citas").get_json()} == {beto.usuario["id"]}


# RN-014 · §8.2 · Bloqueo de 15 minutos tras 3 intentos fallidos
def _login(api, email, clave):
    return api.post("/login", json={"email": email, "clave": clave})


@pytest.mark.regla("RN-014")
def test_rn014_tras_3_intentos_fallidos_la_cuenta_se_bloquea(api, crear_cliente, clave):
    email = crear_cliente().usuario["email"]
    for _ in range(3):
        assert _login(api, email, "equivocada").status_code == 401
    r = _login(api, email, clave)
    assert r.status_code == 423, f"tras 3 intentos fallidos entró con la clave correcta (respuesta {r.status_code})"


@pytest.mark.regla("RN-014")
def test_rn014_el_bloqueo_dura_15_minutos(api, crear_cliente, reloj, clave):
    email = crear_cliente().usuario["email"]
    for _ in range(4):
        _login(api, email, "equivocada")
    reloj.avanzar(minutes=16)
    assert _login(api, email, clave).status_code == 200


@pytest.mark.regla("RN-014")
def test_rn014_dos_fallos_no_bloquean(api, crear_cliente, clave):
    email = crear_cliente().usuario["email"]
    for _ in range(2):
        _login(api, email, "equivocada")
    assert _login(api, email, clave).status_code == 200


# RN-015 · §8.3 · Permisos por rol (duda resuelta: matriz del equipo)
ROLES = ("cliente", "recepcion", "admin")


def _acciones(como, servicio, profesional, otro):
    return {
        "crear servicio": (lambda c: c.post("/servicios", json={"nombre": "Nuevo", "duracion_min": 30, "precio": "100"}), {"admin"}),
        "cambiar precio": (lambda c: c.patch(f"/servicios/{servicio['id']}", json={"precio": "900"}), {"admin"}),
        "crear profesional": (lambda c: c.post("/profesionales", json={"nombre": "Nueva"}), {"admin"}),
        "marcar premium": (lambda c: c.patch(f"/clientes/{otro.usuario['id']}", json={"premium": True}), {"admin"}),
        "ver agenda": (lambda c: c.get(f"/profesionales/{profesional['id']}/agenda"), {"recepcion", "admin"}),
        "reservar para otro cliente": (lambda c: c.post("/citas", json={
            "servicio_id": servicio["id"], "profesional_id": profesional["id"], "inicio": "2026-12-04T10:00", "cliente_id": otro.usuario["id"],
        }), {"recepcion", "admin"}),
        "enviar recordatorios": (lambda c: c.post("/tareas/recordatorios"), {"recepcion", "admin"}),
        "ver reporte de anticipos": (lambda c: c.get("/reportes/anticipos"), {"admin"}),
    }


ACCIONES = ["crear servicio", "cambiar precio", "crear profesional", "marcar premium", "ver agenda",
            "reservar para otro cliente", "enviar recordatorios", "ver reporte de anticipos"]
CASOS = [(a, r) for a in ACCIONES for r in ROLES]


@pytest.mark.regla("RN-015")
@pytest.mark.parametrize(("accion", "rol"), CASOS, ids=[f"{a}-{r}" for a, r in CASOS])
def test_rn015_matriz_de_permisos(como, crear_cliente, servicio, profesional, accion, rol):
    hacer, permitidos = _acciones(como, servicio, profesional, crear_cliente())[accion]
    r = hacer(como(rol))
    if rol in permitidos:
        assert r.status_code != 403, f"{rol} debería poder «{accion}»"
    else:
        assert r.status_code == 403, f"{rol} no debería poder «{accion}» (respuesta {r.status_code})"
