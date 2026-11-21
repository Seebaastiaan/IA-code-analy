"""Error de negocio con su código HTTP; la app lo responde como {"error": mensaje}."""


class Error(Exception):
    def __init__(self, status: int, mensaje: str):
        super().__init__(mensaje)
        self.status = status
        self.mensaje = mensaje
