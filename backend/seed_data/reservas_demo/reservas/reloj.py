"""Hora del sistema en un solo lugar (hora local del centro, sin zona). Las pruebas la fijan con monkeypatch."""

from datetime import datetime


def ahora() -> datetime:
    return datetime.now().replace(microsecond=0)
