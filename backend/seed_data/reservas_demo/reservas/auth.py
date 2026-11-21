"""Inicio de sesión (con bloqueo tras intentos fallidos), usuario actual y permisos por rol."""

import secrets
from datetime import timedelta
from functools import wraps

from flask import g, request
from sqlalchemy import select
from werkzeug.security import check_password_hash

from reservas import reloj
from reservas.errores import Error
from reservas.modelos import Usuario

ROLES = ("cliente", "recepcion", "admin")
INTENTOS_MAXIMOS = 3
BLOQUEO = timedelta(minutes=15)


def iniciar_sesion(db, email: str, clave: str) -> str:
    usuario = db.scalar(select(Usuario).where(Usuario.email == email.strip().lower()))
    if usuario is None:
        raise Error(401, "Correo o contraseña incorrectos")
    ahora = reloj.ahora()
    if usuario.bloqueado_hasta and ahora < usuario.bloqueado_hasta:
        raise Error(423, "Cuenta bloqueada por intentos fallidos; intenta más tarde")
    if not check_password_hash(usuario.clave_hash, clave):
        usuario.intentos_fallidos += 1
        if usuario.intentos_fallidos > INTENTOS_MAXIMOS:
            usuario.bloqueado_hasta = ahora + BLOQUEO
            usuario.intentos_fallidos = 0
        db.commit()
        raise Error(401, "Correo o contraseña incorrectos")
    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    usuario.token = secrets.token_urlsafe(24)
    db.commit()
    return usuario.token


def usuario_actual() -> Usuario:
    cabecera = request.headers.get("Authorization", "")
    if not cabecera.startswith("Bearer "):
        raise Error(401, "Falta el token")
    usuario = g.db.scalar(select(Usuario).where(Usuario.token == cabecera.removeprefix("Bearer ").strip()))
    if usuario is None:
        raise Error(401, "Token inválido")
    return usuario


def requiere(*roles: str):
    """Decorador de ruta: deja pasar solo a esos roles y deja al usuario en `g.usuario`."""

    def decorar(vista):
        @wraps(vista)
        def envuelta(*args, **kwargs):
            g.usuario = usuario_actual()
            if g.usuario.rol not in roles:
                raise Error(403, f"El rol {g.usuario.rol} no puede hacer esto")
            return vista(*args, **kwargs)

        return envuelta

    return decorar
