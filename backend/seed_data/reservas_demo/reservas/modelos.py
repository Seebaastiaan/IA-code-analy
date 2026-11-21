"""Tablas de las reservas."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from reservas.db import Base


class Dinero(TypeDecorator):
    """Decimal guardado como texto: SQLite no tiene un tipo decimal exacto."""

    impl = String(30)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else str(Decimal(value))

    def process_result_value(self, value, dialect):
        return None if value is None else Decimal(value)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(120), unique=True)
    telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    clave_hash: Mapped[str] = mapped_column(String(200))
    # cliente | recepcion | admin
    rol: Mapped[str] = mapped_column(String(20), default="cliente")
    premium: Mapped[bool] = mapped_column(Boolean, default=False)
    token: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Servicio(Base):
    __tablename__ = "servicios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))
    duracion_min: Mapped[int]
    precio: Mapped[Decimal] = mapped_column(Dinero)


class Profesional(Base):
    __tablename__ = "profesionales"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80))


class Cita(Base):
    __tablename__ = "citas"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    servicio_id: Mapped[int] = mapped_column(ForeignKey("servicios.id"))
    profesional_id: Mapped[int] = mapped_column(ForeignKey("profesionales.id"))
    inicio: Mapped[datetime] = mapped_column(DateTime)
    fin: Mapped[datetime] = mapped_column(DateTime)
    # confirmada | cancelada
    estado: Mapped[str] = mapped_column(String(20), default="confirmada")
    anticipo: Mapped[Decimal] = mapped_column(Dinero)
    reembolso: Mapped[Decimal | None] = mapped_column(Dinero, nullable=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime)
    cancelada_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recordatorio_enviado: Mapped[bool] = mapped_column(Boolean, default=False)

    cliente: Mapped[Usuario] = relationship()
    servicio: Mapped[Servicio] = relationship()
    profesional: Mapped[Profesional] = relationship()

    @property
    def folio(self) -> str:
        return f"R-{self.id:05d}"
