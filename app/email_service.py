"""Envío de correos por SMTP para recuperación de contraseña y bienvenida.

La configuración se lee, en este orden, de:
1. Variables de entorno: RAMA_SMTP_HOST, RAMA_SMTP_PORT, RAMA_SMTP_USER,
   RAMA_SMTP_PASSWORD, RAMA_SMTP_FROM (opcional) y RAMA_SMTP_SECURITY
   ("starttls" por defecto, o "ssl").
2. Un archivo ``config/email_settings.json`` junto a este módulo (ver
   ``config/email_settings.example.json``). Ese archivo está en .gitignore
   para no subir credenciales al repositorio.
"""

from __future__ import annotations

import json
import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from html import escape
from pathlib import Path

APP_NAME = "Rama | Retiro de poda"
SETTINGS_FILE = Path(__file__).with_name("config") / "email_settings.json"
SMTP_TIMEOUT_SECONDS = 15


class EmailConfigError(RuntimeError):
    """El correo no está configurado en este equipo."""


class EmailSendError(RuntimeError):
    """No se pudo entregar el correo al servidor SMTP."""


@dataclass(frozen=True)
class EmailSettings:
    host: str
    port: int
    user: str
    password: str
    sender: str
    security: str = "starttls"


def load_email_settings() -> EmailSettings:
    file_values: dict[str, object] = {}
    if SETTINGS_FILE.exists():
        try:
            file_values = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise EmailConfigError(
                f"No se pudo leer {SETTINGS_FILE.name}: {error}"
            ) from error
        if not isinstance(file_values, dict):
            raise EmailConfigError(f"{SETTINGS_FILE.name} debe ser un objeto JSON.")

    def pick(env_name: str, key: str, default: object = "") -> str:
        value = os.environ.get(env_name)
        if value is None or value == "":
            value = file_values.get(key, default)
        return str(value).strip()

    host = pick("RAMA_SMTP_HOST", "host")
    user = pick("RAMA_SMTP_USER", "user")
    password = pick("RAMA_SMTP_PASSWORD", "password")
    if not host or not user or not password:
        raise EmailConfigError(
            "Falta configurar el correo de envío (host, usuario y contraseña SMTP)."
        )
    security = pick("RAMA_SMTP_SECURITY", "security", "starttls").lower()
    if security not in {"starttls", "ssl"}:
        raise EmailConfigError('La seguridad SMTP debe ser "starttls" o "ssl".')
    default_port = "465" if security == "ssl" else "587"
    try:
        port = int(pick("RAMA_SMTP_PORT", "port", default_port))
    except ValueError as error:
        raise EmailConfigError("El puerto SMTP debe ser un número.") from error
    sender = pick("RAMA_SMTP_FROM", "from", user) or user
    return EmailSettings(host, port, user, password, sender, security)


def _send(message: EmailMessage, settings: EmailSettings) -> None:
    context = ssl.create_default_context()
    try:
        if settings.security == "ssl":
            with smtplib.SMTP_SSL(
                settings.host, settings.port,
                timeout=SMTP_TIMEOUT_SECONDS, context=context,
            ) as server:
                server.login(settings.user, settings.password)
                server.send_message(message)
        else:
            with smtplib.SMTP(
                settings.host, settings.port, timeout=SMTP_TIMEOUT_SECONDS,
            ) as server:
                server.starttls(context=context)
                server.login(settings.user, settings.password)
                server.send_message(message)
    except smtplib.SMTPAuthenticationError as error:
        raise EmailSendError(
            "El servidor rechazó el usuario o la contraseña SMTP."
        ) from error
    except (smtplib.SMTPException, OSError) as error:
        raise EmailSendError(f"No se pudo enviar el correo: {error}") from error


def _build_message(
    settings: EmailSettings, to_address: str, subject: str,
    text_body: str, html_body: str,
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{APP_NAME} <{settings.sender}>"
    message["To"] = to_address
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    return message


def send_welcome_email(to_address: str, name: str) -> None:
    """Envía «Felicidades por ser nuevo usuario» a una cuenta recién creada."""
    settings = load_email_settings()
    first_name = escape(name.strip().split(" ")[0] or "ciudadano")
    text_body = (
        f"¡Felicidades, {name.strip()}!\n\n"
        f"Felicidades por ser nuevo usuario de {APP_NAME}. "
        "Tu cuenta fue creada correctamente y ya puedes iniciar sesión "
        "para solicitar el retiro de ramas y restos de poda.\n\n"
        "Si no creaste esta cuenta, ignora este mensaje."
    )
    html_body = f"""\
<html><body style="font-family:Arial,sans-serif;color:#1C2E27;">
  <h2 style="color:#173E31;">¡Felicidades, {first_name}!</h2>
  <p>Felicidades por ser nuevo usuario de <b>{escape(APP_NAME)}</b>.</p>
  <p>Tu cuenta fue creada correctamente y ya puedes iniciar sesión para
  solicitar el retiro de ramas y restos de poda.</p>
  <p style="color:#49564E;font-size:13px;">
  Si no creaste esta cuenta, ignora este mensaje.</p>
</body></html>"""
    message = _build_message(
        settings, to_address, "¡Felicidades por ser nuevo usuario!",
        text_body, html_body,
    )
    _send(message, settings)


def send_password_reset_email(
    to_address: str, name: str, code: str, minutes_valid: int,
) -> None:
    """Envía el código de verificación para cambiar la contraseña."""
    settings = load_email_settings()
    text_body = (
        f"Hola {name.strip()},\n\n"
        f"Tu código para cambiar la contraseña es: {code}\n\n"
        f"El código vence en {minutes_valid} minutos y solo sirve una vez.\n"
        "Si no pediste este cambio, ignora este mensaje: tu contraseña "
        "actual sigue siendo la misma."
    )
    html_body = f"""\
<html><body style="font-family:Arial,sans-serif;color:#1C2E27;">
  <h2 style="color:#173E31;">Recuperar contraseña</h2>
  <p>Hola {escape(name.strip())}, usa este código en la app:</p>
  <p style="font-size:32px;letter-spacing:8px;font-weight:bold;
  color:#173E31;">{escape(code)}</p>
  <p>Vence en {minutes_valid} minutos y solo sirve una vez.</p>
  <p style="color:#49564E;font-size:13px;">
  Si no pediste este cambio, ignora este mensaje: tu contraseña actual
  sigue siendo la misma.</p>
</body></html>"""
    message = _build_message(
        settings, to_address, f"Tu código de recuperación: {code}",
        text_body, html_body,
    )
    _send(message, settings)
