"""Reglas de las citas: horario, traslapes, anticipo, cancelación con reembolso, avisos y recordatorios."""

from datetime import datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select

from reservas import correo, reloj
from reservas.errores import Error
from reservas.modelos import Cita, Profesional, Servicio, Usuario

APERTURA = time(9, 0)
CIERRE = time(20, 0)
# Lunes (0) a sábado (5)
ULTIMO_DIA = 5
ANTICIPACION_MINIMA = timedelta(hours=2)
CITAS_ACTIVAS_MAXIMAS = 3
PORCENTAJE_ANTICIPO = Decimal("0.30")
LIMITE_CANCELACION = timedelta(hours=24)
LIMITE_CANCELACION_PREMIUM = timedelta(hours=12)
VENTANA_RECORDATORIO = timedelta(hours=24)
CENTAVO = Decimal("0.01")


def dinero(valor: Decimal) -> Decimal:
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def fecha_legible(momento: datetime) -> str:
    return momento.strftime("%d/%m/%Y a las %H:%M")


def a_json(cita: Cita) -> dict:
    return {
        "id": cita.id, "folio": cita.folio, "cliente_id": cita.cliente_id, "servicio_id": cita.servicio_id,
        "servicio": cita.servicio.nombre, "profesional_id": cita.profesional_id, "inicio": cita.inicio.isoformat(),
        "fin": cita.fin.isoformat(), "estado": cita.estado, "anticipo": str(cita.anticipo),
        "reembolso": None if cita.reembolso is None else str(cita.reembolso),
    }


def _en_horario(inicio: datetime, fin: datetime) -> bool:
    return inicio.weekday() <= ULTIMO_DIA and inicio.date() == fin.date() and inicio.time() >= APERTURA and fin.time() <= CIERRE


def reservar(db, cliente: Usuario, servicio: Servicio, profesional: Profesional, inicio: datetime) -> Cita:
    ahora = reloj.ahora()
    fin = inicio + timedelta(minutes=servicio.duracion_min)
    if not _en_horario(inicio, fin):
        raise Error(409, "La cita queda fuera del horario de atención (lunes a sábado de 9:00 a 20:00)")
    if inicio - ahora < ANTICIPACION_MINIMA:
        raise Error(409, "Las citas se reservan con al menos 2 horas de anticipación")
    activas = db.scalar(
        select(func.count()).select_from(Cita).where(Cita.cliente_id == cliente.id, Cita.estado == "confirmada", Cita.inicio > ahora)
    )
    if activas >= CITAS_ACTIVAS_MAXIMAS:
        raise Error(409, f"Ya tienes {CITAS_ACTIVAS_MAXIMAS} citas activas")
    ocupado = db.scalar(select(Cita.id).where(Cita.profesional_id == profesional.id, Cita.estado == "confirmada", Cita.inicio == inicio))
    if ocupado is not None:
        raise Error(409, f"{profesional.nombre} ya tiene una cita a esa hora")
    empalme = db.scalar(
        select(Cita.id).where(Cita.cliente_id == cliente.id, Cita.estado == "confirmada", Cita.inicio < fin, Cita.fin > inicio)
    )
    if empalme is not None:
        raise Error(409, "Ya tienes otra cita en ese horario")
    cita = Cita(
        cliente_id=cliente.id, servicio_id=servicio.id, profesional_id=profesional.id, inicio=inicio, fin=fin,
        estado="confirmada", anticipo=dinero(servicio.precio * PORCENTAJE_ANTICIPO), creada_en=ahora,
    )
    db.add(cita)
    db.flush()
    correo.enviar(
        cliente.email, f"Cita confirmada · folio {cita.folio}",
        f"Hola {cliente.nombre}: tu cita de {servicio.nombre} con {profesional.nombre} quedó confirmada para el "
        f"{fecha_legible(inicio)}. Folio: {cita.folio}. Anticipo pagado: ${cita.anticipo}.",
    )
    return cita


def cancelar(db, cita: Cita) -> Cita:
    ahora = reloj.ahora()
    if cita.estado != "confirmada":
        raise Error(409, "La cita ya estaba cancelada")
    if cita.inicio <= ahora:
        raise Error(409, "La cita ya empezó; no se puede cancelar")
    limite = LIMITE_CANCELACION_PREMIUM if cita.cliente.premium else LIMITE_CANCELACION
    reembolso = cita.anticipo if cita.inicio - ahora > limite else Decimal("0.00")
    cita.estado = "cancelada"
    cita.cancelada_en = ahora
    cita.reembolso = dinero(reembolso)
    correo.enviar(
        cita.cliente.email, f"Cita cancelada · folio {cita.folio}",
        f"Hola {cita.cliente.nombre}: cancelamos tu cita del {fecha_legible(cita.inicio)}. "
        f"Reembolso del anticipo: ${cita.reembolso}.",
    )
    return cita


def enviar_recordatorios(db) -> int:
    """Tarea periódica (cron): avisa una sola vez de cada cita que empieza en las próximas 24 horas."""
    ahora = reloj.ahora()
    pendientes = db.scalars(select(Cita).where(
        Cita.estado == "confirmada", Cita.recordatorio_enviado.is_(False), Cita.inicio > ahora, Cita.inicio <= ahora + VENTANA_RECORDATORIO,
    )).all()
    for cita in pendientes:
        correo.enviar(
            cita.cliente.email, f"Recordatorio · folio {cita.folio}",
            f"Hola {cita.cliente.nombre}: te esperamos el {fecha_legible(cita.inicio)} para tu {cita.servicio.nombre}.",
        )
        cita.recordatorio_enviado = True
    return len(pendientes)
