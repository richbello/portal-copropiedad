"""Notificaciones dentro del portal y, si hay SMTP configurado, por correo."""
import logging
import os
import smtplib
from email.message import EmailMessage

from sqlalchemy.orm import Session

from . import models

log = logging.getLogger("notificaciones")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "no-reply@conjunto.local")


def notificar(db: Session, usuario: models.Usuario, titulo: str, texto: str, enlace: str | None = None):
    db.add(models.Notificacion(usuario_id=usuario.id, titulo=titulo, texto=texto, enlace=enlace))
    enviar_correo(usuario.email, titulo, texto)


def enviar_correo(destino: str, asunto: str, cuerpo: str) -> None:
    if not SMTP_HOST:
        log.info("[correo simulado] para=%s asunto=%s", destino, asunto)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = SMTP_FROM, destino, asunto
    msg.set_content(cuerpo)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
            s.starttls()
            if SMTP_USER:
                s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
    except Exception as e:  # el correo nunca debe tumbar la operación
        log.warning("No se pudo enviar correo a %s: %s", destino, e)
