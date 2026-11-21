"""
API de reservas (Flask).

    flask --app "reservas.app:crear_app()" crear-admin admin@sereno.example una-clave
    flask --app "reservas.app:crear_app()" run --debug
"""

import os
from datetime import datetime
from decimal import Decimal, InvalidOperation

import click
from flask import Flask, g, jsonify, request
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from reservas import citas, db
from reservas.auth import iniciar_sesion, requiere
from reservas.errores import Error
from reservas.modelos import Cita, Profesional, Servicio, Usuario

PERSONAL = ("recepcion", "admin")
TODOS = ("cliente", "recepcion", "admin")


def _cuerpo(*obligatorios: str) -> dict:
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        raise Error(422, "Envía un JSON")
    faltan = [c for c in obligatorios if datos.get(c) in (None, "")]
    if faltan:
        raise Error(422, f"Falta {', '.join(faltan)}")
    return datos


def _entero(valor, campo: str) -> int:
    try:
        numero = int(valor)
    except (TypeError, ValueError) as exc:
        raise Error(422, f"`{campo}` debe ser un número entero") from exc
    if numero <= 0:
        raise Error(422, f"`{campo}` debe ser mayor a 0")
    return numero


def _precio(valor) -> Decimal:
    try:
        precio = Decimal(str(valor))
    except InvalidOperation as exc:
        raise Error(422, "`precio` no es un número") from exc
    if precio <= 0:
        raise Error(422, "`precio` debe ser mayor a 0")
    return citas.dinero(precio)


def _fecha(valor) -> datetime:
    try:
        return datetime.fromisoformat(str(valor)).replace(tzinfo=None, microsecond=0)
    except ValueError as exc:
        raise Error(422, "`inicio` debe ser una fecha ISO, p. ej. 2026-12-02T10:00") from exc


def _obtener(modelo, id_: int, nombre: str):
    obj = g.db.get(modelo, id_)
    if obj is None:
        raise Error(404, f"No existe {nombre}")
    return obj


def _servicio_json(s: Servicio) -> dict:
    return {"id": s.id, "nombre": s.nombre, "duracion_min": s.duracion_min, "precio": str(s.precio)}


def _cliente_json(u: Usuario) -> dict:
    return {"id": u.id, "nombre": u.nombre, "email": u.email, "premium": u.premium}


def crear_app(url: str | None = None) -> Flask:
    app = Flask(__name__)
    db.configurar(url or os.getenv("RESERVAS_DB", "sqlite:///reservas.db"))

    @app.before_request
    def abrir():
        g.db = db.sesion()

    @app.teardown_request
    def cerrar(_exc):
        sesion = g.pop("db", None)
        if sesion is not None:
            sesion.close()

    @app.errorhandler(Error)
    def error(exc: Error):
        return jsonify({"error": exc.mensaje}), exc.status

    # ───────── Cuentas ─────────

    @app.post("/clientes")
    def registrar():
        d = _cuerpo("nombre", "email", "clave")
        email = str(d["email"]).strip().lower()
        if g.db.scalar(select(Usuario.id).where(Usuario.email == email)) is not None:
            raise Error(409, "Ya hay una cuenta con ese correo")
        if len(str(d["clave"])) < 8:
            raise Error(422, "La contraseña debe tener al menos 8 caracteres")
        u = Usuario(nombre=str(d["nombre"]), email=email, telefono=d.get("telefono"), clave_hash=generate_password_hash(str(d["clave"])), rol="cliente")
        g.db.add(u)
        g.db.commit()
        return jsonify(_cliente_json(u)), 201

    @app.post("/login")
    def login():
        d = _cuerpo("email", "clave")
        return jsonify({"token": iniciar_sesion(g.db, str(d["email"]), str(d["clave"]))})

    @app.patch("/clientes/<int:cliente_id>")
    @requiere("admin")
    def marcar_premium(cliente_id: int):
        u = _obtener(Usuario, cliente_id, "el cliente")
        u.premium = bool(_cuerpo("premium")["premium"])
        g.db.commit()
        return jsonify(_cliente_json(u))

    # ───────── Catálogo ─────────

    @app.get("/servicios")
    def servicios():
        return jsonify([_servicio_json(s) for s in g.db.scalars(select(Servicio).order_by(Servicio.id))])

    @app.post("/servicios")
    @requiere("admin")
    def crear_servicio():
        d = _cuerpo("nombre", "duracion_min", "precio")
        s = Servicio(nombre=str(d["nombre"]), duracion_min=_entero(d["duracion_min"], "duracion_min"), precio=_precio(d["precio"]))
        g.db.add(s)
        g.db.commit()
        return jsonify(_servicio_json(s)), 201

    @app.patch("/servicios/<int:servicio_id>")
    @requiere("admin")
    def cambiar_precio(servicio_id: int):
        s = _obtener(Servicio, servicio_id, "el servicio")
        s.precio = _precio(_cuerpo("precio")["precio"])
        g.db.commit()
        return jsonify(_servicio_json(s))

    @app.post("/profesionales")
    @requiere("admin")
    def crear_profesional():
        p = Profesional(nombre=str(_cuerpo("nombre")["nombre"]))
        g.db.add(p)
        g.db.commit()
        return jsonify({"id": p.id, "nombre": p.nombre}), 201

    @app.get("/profesionales/<int:profesional_id>/agenda")
    @requiere(*PERSONAL)
    def agenda(profesional_id: int):
        _obtener(Profesional, profesional_id, "el profesional")
        lista = g.db.scalars(select(Cita).where(Cita.profesional_id == profesional_id, Cita.estado == "confirmada").order_by(Cita.inicio))
        return jsonify([citas.a_json(c) for c in lista])

    # ───────── Citas ─────────

    @app.post("/citas")
    @requiere(*TODOS)
    def reservar():
        d = _cuerpo("servicio_id", "profesional_id", "inicio")
        if g.usuario.rol == "cliente":
            if d.get("cliente_id") not in (None, g.usuario.id):
                raise Error(403, "Un cliente solo reserva para sí mismo")
            cliente = g.usuario
        else:
            cliente = _obtener(Usuario, _entero(d.get("cliente_id"), "cliente_id"), "el cliente")
        servicio = _obtener(Servicio, _entero(d["servicio_id"], "servicio_id"), "el servicio")
        profesional = _obtener(Profesional, _entero(d["profesional_id"], "profesional_id"), "el profesional")
        cita = citas.reservar(g.db, cliente, servicio, profesional, _fecha(d["inicio"]))
        g.db.commit()
        return jsonify(citas.a_json(cita)), 201

    @app.get("/citas")
    @requiere(*TODOS)
    def mis_citas():
        consulta = select(Cita).order_by(Cita.inicio)
        if g.usuario.rol == "cliente":
            consulta = consulta.where(Cita.cliente_id == g.usuario.id)
        return jsonify([citas.a_json(c) for c in g.db.scalars(consulta)])

    @app.get("/citas/<int:cita_id>")
    @requiere(*TODOS)
    def ver_cita(cita_id: int):
        return jsonify(citas.a_json(_obtener(Cita, cita_id, "la cita")))

    @app.post("/citas/<int:cita_id>/cancelar")
    @requiere(*TODOS)
    def cancelar(cita_id: int):
        cita = _obtener(Cita, cita_id, "la cita")
        if g.usuario.rol == "cliente" and cita.cliente_id != g.usuario.id:
            raise Error(404, "No existe la cita")
        citas.cancelar(g.db, cita)
        g.db.commit()
        return jsonify(citas.a_json(cita))

    # ───────── Tareas y reportes ─────────

    @app.post("/tareas/recordatorios")
    @requiere(*PERSONAL)
    def recordatorios():
        enviados = citas.enviar_recordatorios(g.db)
        g.db.commit()
        return jsonify({"enviados": enviados})

    @app.get("/reportes/anticipos")
    @requiere("admin")
    def reporte():
        cobrado = sum((c.anticipo for c in g.db.scalars(select(Cita))), Decimal(0))
        devuelto = sum((c.reembolso or 0 for c in g.db.scalars(select(Cita))), Decimal(0))
        return jsonify({"cobrado": str(cobrado), "reembolsado": str(devuelto), "neto": str(cobrado - devuelto)})

    @app.cli.command("crear-admin")
    @click.argument("email")
    @click.argument("clave")
    def crear_admin(email: str, clave: str):
        """Crea un usuario administrador."""
        with db.sesion() as s:
            s.add(Usuario(nombre="Administración", email=email.lower(), clave_hash=generate_password_hash(clave), rol="admin"))
            s.commit()
        click.echo(f"Administrador {email} creado")

    return app
