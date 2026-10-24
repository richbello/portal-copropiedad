"""Contraseñas, tokens JWT y control de acceso por rol."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import models
from .config import JWT_ALGORITHM, SECRET_KEY, TOKEN_MINUTOS
from .db import get_db

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verificar_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def validar_fortaleza(password: str) -> None:
    errores = []
    if len(password) < 8:
        errores.append("mínimo 8 caracteres")
    if not any(c.isdigit() for c in password):
        errores.append("al menos un número")
    if not any(c.isalpha() for c in password):
        errores.append("al menos una letra")
    if errores:
        raise HTTPException(400, "La contraseña debe tener " + ", ".join(errores))


def crear_token(usuario: models.Usuario) -> str:
    payload = {
        "sub": str(usuario.id),
        "rol": usuario.rol,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTOS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def usuario_actual(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> models.Usuario:
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No autenticado")
    try:
        payload = jwt.decode(cred.credentials, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "La sesión expiró, ingrese de nuevo")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")
    usuario = db.get(models.Usuario, int(payload["sub"]))
    if not usuario or not usuario.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario inactivo")
    return usuario


def requiere_rol(*roles: str):
    def _dep(usuario: models.Usuario = Depends(usuario_actual)) -> models.Usuario:
        if usuario.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tiene permiso para esta acción")
        return usuario
    return _dep


def unidades_del_usuario(usuario: models.Usuario) -> list[int]:
    return [uu.unidad_id for uu in usuario.unidades]


def verificar_acceso_unidad(usuario: models.Usuario, unidad_id: int) -> None:
    """Un propietario solo ve sus unidades. Roles de gestión/control ven todas."""
    if usuario.rol in models.ROLES_LECTURA_GLOBAL:
        return
    if unidad_id not in unidades_del_usuario(usuario):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No tiene acceso a esta unidad")


def auditar(db: Session, usuario_id: int | None, accion: str, detalle: str = "", request: Request | None = None):
    ip = request.client.host if request and request.client else None
    db.add(models.Auditoria(usuario_id=usuario_id, accion=accion, detalle=detalle, ip=ip))
