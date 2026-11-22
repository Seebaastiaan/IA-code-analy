"""
Datos de ejemplo para probar la interfaz (opcional):

    python -m reservas.datos_demo

Crea servicios, profesionales, cuatro cuentas y un par de citas próximas, con las mismas funciones que la API. No hace
nada si ya hay servicios. Las contraseñas son de demostración: no las uses en ningún otro lado.
"""

import os
from datetime import datetime, timedelta

from sqlalchemy import select
from werkzeug.security import generate_password_hash

from reservas import citas, db
from reservas.modelos import Profesional, Servicio, Usuario

CLAVE = "demo-clave-1234"
CUENTAS = (
    ("Administración", "admin@sereno.example", "admin", False),
    ("Recepción", "recepcion@sereno.example", "recepcion", False),
    ("Ana Cliente (premium)", "ana@sereno.example", "cliente", True),
    ("Luis Cliente", "luis@sereno.example", "cliente", False),
)


def _proximo_dia_habil(desde: datetime, hora: int) -> datetime:
    dia = desde + timedelta(days=1)
    while dia.weekday() > citas.ULTIMO_DIA:
        dia += timedelta(days=1)
    return dia.replace(hour=hora, minute=0, second=0, microsecond=0)


def sembrar(url: str | None = None) -> str:
    db.configurar(url or os.getenv("RESERVAS_DB", "sqlite:///reservas.db"))
    with db.sesion() as s:
        if s.scalar(select(Servicio.id)) is not None:
            return "Ya hay servicios: no se agregó nada."
        usuarios = {}
        for nombre, email, rol, premium in CUENTAS:
            usuarios[email] = Usuario(nombre=nombre, email=email, rol=rol, premium=premium, clave_hash=generate_password_hash(CLAVE))
            s.add(usuarios[email])
        masaje = Servicio(nombre="Masaje relajante", duracion_min=60, precio=800)
        facial = Servicio(nombre="Facial", duracion_min=45, precio=600)
        reflexo = Servicio(nombre="Reflexología", duracion_min=30, precio=400)
        marta, diego = Profesional(nombre="Marta"), Profesional(nombre="Diego")
        s.add_all([masaje, facial, reflexo, marta, diego])
        s.flush()
        manana = _proximo_dia_habil(datetime.now(), 10)
        citas.reservar(s, usuarios["ana@sereno.example"], masaje, marta, manana)
        citas.reservar(s, usuarios["luis@sereno.example"], facial, diego, manana + timedelta(hours=2))
        s.commit()
    return f"Listo. Cuentas (contraseña {CLAVE}): " + ", ".join(email for _, email, _, _ in CUENTAS)


if __name__ == "__main__":
    print(sembrar())
