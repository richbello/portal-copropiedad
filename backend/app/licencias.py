"""Licencias de prueba para conocer el portal (solo en el servidor de demostración).

Una licencia es un código firmado con la fecha de vencimiento y el nombre del conjunto interesado.
No se guarda en la base de datos: el servidor de demostración reinicia sus datos ficticios con
frecuencia, y la firma basta para saber si el código es auténtico y si sigue vigente.
"""
import base64
import hashlib
import hmac
import json
from datetime import date, datetime, timedelta, timezone

from .config import SECRET_KEY

# Usuarios que usa una licencia: primero los de la demostración; si no existen, unos propios de prueba
PERFILES = {"administrador": "admin@conjunto.co", "propietario": "propietario@conjunto.co"}
PERFILES_PRUEBA = {"administrador": "prueba.admin@verde360.co", "propietario": "prueba.propietario@verde360.co"}
PROTEGIDOS = set(PERFILES.values()) | set(PERFILES_PRUEBA.values())

COLOMBIA = timezone(timedelta(hours=-5))  # Colombia no tiene horario de verano


def hoy() -> date:
    return datetime.now(COLOMBIA).date()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _firma(cuerpo: str) -> str:
    return _b64(hmac.new(SECRET_KEY.encode(), b"licencia:" + cuerpo.encode(), hashlib.sha256).digest()[:12])


def generar(conjunto: str, dias: int = 15, contacto: str = "", vence: date | None = None) -> dict:
    vence = vence or hoy() + timedelta(days=dias)
    datos = {"c": conjunto.strip()[:80], "v": vence.isoformat(), "k": contacto.strip()[:80]}
    cuerpo = _b64(json.dumps(datos, ensure_ascii=False, separators=(",", ":")).encode())
    return {"codigo": f"{cuerpo}.{_firma(cuerpo)}", "conjunto": datos["c"], "vence": datos["v"]}


class LicenciaInvalida(ValueError):
    pass


def verificar(codigo: str) -> dict:
    codigo = (codigo or "").strip()
    try:
        cuerpo, firma = codigo.split(".", 1)
    except ValueError:
        raise LicenciaInvalida("El código de licencia no es válido")
    if not hmac.compare_digest(firma, _firma(cuerpo)):
        raise LicenciaInvalida("El código de licencia no es válido")
    datos = json.loads(_unb64(cuerpo))
    vence = date.fromisoformat(datos["v"])
    if vence < hoy():
        raise LicenciaInvalida(f"Esta licencia de prueba venció el {vence.strftime('%d/%m/%Y')}. "
                               "Escríbanos para ampliarla o activar el portal de su conjunto.")
    return {"conjunto": datos["c"], "vence": vence, "contacto": datos.get("k", "")}


def fin_del_dia(d: date) -> datetime:
    """La licencia vale hasta las 11:59 p. m. (hora de Colombia) del día de vencimiento."""
    return datetime.combine(d, datetime.max.time().replace(microsecond=0), tzinfo=COLOMBIA)
