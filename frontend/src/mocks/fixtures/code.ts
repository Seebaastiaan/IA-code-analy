/** Archivos del repositorio de ejemplo (equipo/api-pagos). Los números de línea de los hallazgos dependen de ellos. */
export const FILES: Record<string, string> = {
  'auth.py': `import hashlib
import os

import jwt
from datetime import datetime, timedelta

from .db import obtener_usuario

ALGORITMO = "HS256"
EXPIRACION_MIN = 30


def crear_token(usuario_id: int) -> str:
    carga = {"sub": usuario_id, "exp": datetime.utcnow() + timedelta(minutes=EXPIRACION_MIN)}
    SECRET_KEY = "super-secreto-123"
    return jwt.encode(carga, SECRET_KEY, algorithm=ALGORITMO)


def verificar(usuario: str, clave: str) -> bool:
    u = obtener_usuario(usuario)
    return u is not None and u.clave_hash == hashlib.sha256(clave.encode()).hexdigest()
`,
  'api.py': `import sqlite3

import os
from fastapi import FastAPI, HTTPException

app = FastAPI()
conexion = sqlite3.connect("pagos.db", check_same_thread=False)


@app.get("/pagos/{cliente}")
def listar_pagos(cliente: str):
    # Devuelve los pagos de un cliente
    cursor = conexion.cursor()
    if not cliente:
        raise HTTPException(status_code=400)
    # TODO: paginar resultados
    consulta = "SELECT * FROM pagos WHERE cliente = '" + cliente + "'"
    filas = cursor.execute(consulta).fetchall()
    return {"cliente": cliente, "pagos": filas}
`,
  'utils.py': `import hashlib
import json


def huella(texto: str) -> str:
    # Huella usada para validar contraseñas temporales
    datos = texto.strip().encode()
    # TODO: revisar algoritmo
    return hashlib.md5(datos).hexdigest()


def cargar_config(ruta: str) -> dict:
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def agregar(item, lista=[]):
    lista.append(item)
    return lista
`,
  'tokens.py': `import random
import string

ALFABETO = string.ascii_letters + string.digits


def token_reembolso(longitud: int = 24) -> str:
    # Token de un solo uso para confirmar reembolsos
    return "".join(random.choice(ALFABETO) for _ in range(longitud))
`,
  'requirements.txt': `fastapi==0.110.0
uvicorn==0.29.0
pyjwt==2.8.0
requests==2.25.1
pytest==8.1.1
coverage==7.4.4
`,
  'pagos/procesador.py': `from decimal import Decimal

from .reembolsos import calcular_reembolso


def validar_tarjeta(numero: str) -> bool:
    digitos = [int(d) for d in numero if d.isdigit()]
    if len(digitos) < 13:
        return False
    total = 0
    for i, d in enumerate(reversed(digitos)):
        if i % 2:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def procesar_lote(pagos: list[dict]) -> dict:
    resultado = {"ok": [], "rechazados": [], "reembolsos": []}
    for pago in pagos:
        if not pago.get("monto"):
            resultado["rechazados"].append(pago)
            continue
        if pago.get("moneda") not in ("MXN", "USD", "EUR"):
            resultado["rechazados"].append(pago)
            continue
        if pago.get("tipo") == "reembolso":
            if pago.get("parcial"):
                resultado["reembolsos"].append(calcular_reembolso(pago, parcial=True))
            else:
                resultado["reembolsos"].append(calcular_reembolso(pago, parcial=False))
            continue
        if not validar_tarjeta(pago.get("tarjeta", "")):
            resultado["rechazados"].append(pago)
            continue
        resultado["ok"].append({"id": pago["id"], "monto": Decimal(pago["monto"]), "moneda": pago["moneda"], "estado": "cobrado"})
    return resultado
`,
  'pagos/reembolsos.py': `from decimal import Decimal


def calcular_reembolso(pago: dict, parcial: bool = False) -> dict:
    monto = Decimal(pago["monto"])
    if parcial:
        monto = monto * Decimal(pago.get("porcentaje", 50)) / 100
    if monto <= 0:
        raise ValueError("Monto inválido")
    if pago.get("comision"):
        monto -= Decimal(pago["comision"])
    return {"id": pago["id"], "monto": monto, "parcial": parcial}
`,
  'tests/test_api.py': `from fastapi.testclient import TestClient

from app.api import app

cliente = TestClient(app)


def test_listar_pagos():
    r = cliente.get("/pagos/ana")
    assert r.status_code == 200


def test_crear_pago_invalido():
    r = cliente.post("/pagos", json={"monto": -5})
    assert r.status_code == 400
`,
  'tests/test_auth.py': `import pytest

from app.auth import crear_token, verificar


@pytest.mark.skip(reason="requiere base de datos")
def test_verificar_ok():
    assert verificar("ana", "1234")


@pytest.mark.skip(reason="requiere base de datos")
def test_verificar_mal():
    assert not verificar("ana", "otra")


@pytest.mark.skip(reason="lento")
def test_token_expira():
    assert crear_token(1)
`,
  'README.md': `# api-pagos

API de pagos del equipo Backend (FastAPI + SQLite).

## Ejecutar

    uv pip install -r requirements.txt
    uvicorn app.api:app --reload
`,
}

export const languageOf = (path: string) =>
  path.endsWith('.py') ? 'python' : path.endsWith('.md') ? 'markdown' : path.endsWith('.toml') ? 'toml' : 'plaintext'

export const lineAt = (content: string, line: number) => content.split('\n')[line - 1] ?? ''
