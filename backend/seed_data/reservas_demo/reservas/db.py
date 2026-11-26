"""Conexión a la base de datos. `configurar` la abre una vez al crear la app (SQLite por defecto)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


fabrica: sessionmaker[Session] | None = None


def configurar(url: str) -> None:
    global fabrica
    opciones: dict = {}
    if url.startswith("sqlite"):
        opciones["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            # En memoria: una sola conexión compartida, o cada sesión vería una base vacía
            opciones["poolclass"] = StaticPool
    engine = create_engine(url, **opciones)
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine, expire_on_commit=False)


def sesion() -> Session:
    if fabrica is None:
        raise RuntimeError("Llama a db.configurar() antes de usar la base")
    return fabrica()
