"""Correos a clientes. Con SMTP_HOST se envían por SMTP; sin él solo se escriben en el log (desarrollo)."""

import logging
import os
import smtplib
from collections import deque
from email.message import EmailMessage

log = logging.getLogger(__name__)
REMITENTE = os.getenv("CORREO_REMITENTE", "citas@sereno.example")
# Los últimos correos enviados, para la bandeja de demostración (/demo/correos)
BANDEJA: deque[dict] = deque(maxlen=50)


def _entregar(mensaje: EmailMessage) -> None:
    host = os.getenv("SMTP_HOST")
    if not host:
        log.info("Correo (sin SMTP) a %s: %s", mensaje["To"], mensaje["Subject"])
        return
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=10) as smtp:
        smtp.starttls()
        if os.getenv("SMTP_USUARIO"):
            smtp.login(os.environ["SMTP_USUARIO"], os.environ.get("SMTP_CLAVE", ""))
        smtp.send_message(mensaje)


def enviar(para: str, asunto: str, cuerpo: str) -> None:
    mensaje = EmailMessage()
    mensaje["From"] = REMITENTE
    mensaje["To"] = para
    mensaje["Subject"] = asunto
    mensaje.set_content(cuerpo)
    BANDEJA.append({"para": para, "asunto": asunto, "cuerpo": cuerpo})
    _entregar(mensaje)
