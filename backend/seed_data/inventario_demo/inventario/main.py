"""
API del inventario.

    uvicorn inventario.main:app --reload

Al arrancar crea las tablas y, si no hay usuarios, uno por rol; sus tokens se imprimen en la terminal.
"""

import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from inventario.auth import ROLES
from inventario.db import Base, SessionLocal, engine
from inventario.modelos import Usuario
from inventario.rutas_operaciones import router as operaciones
from inventario.rutas_productos import router as productos


def preparar_base() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(Usuario.id)) is not None:
            return
        for rol in ROLES:
            usuario = Usuario(nombre=rol.capitalize(), rol=rol, token=secrets.token_urlsafe(24))
            db.add(usuario)
            print(f"  {rol:<12} Authorization: Bearer {usuario.token}")
        db.commit()


@asynccontextmanager
async def ciclo(_: FastAPI) -> AsyncIterator[None]:
    preparar_base()
    yield


app = FastAPI(title="Inventario de la cafetería", version="1.0", lifespan=ciclo)
app.include_router(productos)
app.include_router(operaciones)


@app.get("/salud")
def salud() -> dict:
    return {"ok": True}
