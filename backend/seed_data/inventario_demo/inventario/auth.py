"""Usuario actual (token Bearer) y permisos por rol."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from inventario.db import get_db
from inventario.modelos import Usuario

ROLES = ("cajero", "barista", "gerente", "almacenista")

Db = Annotated[Session, Depends(get_db)]


def usuario_actual(db: Db, authorization: Annotated[str | None, Header()] = None) -> Usuario:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Falta el token")
    usuario = db.scalar(select(Usuario).where(Usuario.token == authorization.removeprefix("Bearer ").strip()))
    if usuario is None:
        raise HTTPException(401, "Token inválido")
    return usuario


Actual = Annotated[Usuario, Depends(usuario_actual)]


def requiere(*roles: str) -> Callable[[Usuario], Usuario]:
    """Dependencia que deja pasar solo a esos roles."""

    def revisar(usuario: Actual) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(403, f"El rol {usuario.rol} no puede hacer esto")
        return usuario

    return revisar
