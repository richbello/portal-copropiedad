import hmac
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import licencias, models
from ..config import (CLAVE_MAESTRA, DIAS_LICENCIA, MAX_INTENTOS_LOGIN, MINUTOS_BLOQUEO,
                      MODO_DEMO, NOMBRE_CONJUNTO)
from ..db import get_db
from ..security import (auditar, crear_token, hash_password, usuario_actual,
                        validar_fortaleza, verificar_password)

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


class LoginIn(BaseModel):
    email: str
    password: str


class CambioPasswordIn(BaseModel):
    actual: str
    nueva: str


def usuario_out(u: models.Usuario) -> dict:
    return {
        "id": u.id, "email": u.email, "nombre": u.nombre, "rol": u.rol, "telefono": u.telefono,
        "debe_cambiar_password": u.debe_cambiar_password,
        "acepto_tratamiento_datos": u.acepto_tratamiento_datos is not None,
        "unidades": [{"id": uu.unidad.id, "etiqueta": uu.unidad.etiqueta, "relacion": uu.relacion,
                      "coeficiente": uu.unidad.coeficiente} for uu in u.unidades],
    }


class LicenciaIn(BaseModel):
    codigo: str
    perfil: str = "administrador"


class GenerarLicenciaIn(BaseModel):
    clave_maestra: str
    conjunto: str
    dias: int = DIAS_LICENCIA
    contacto: str = ""


@router.post("/login")
def login(datos: LoginIn, request: Request, db: Session = Depends(get_db)):
    if MODO_DEMO:
        raise HTTPException(403, "Este es el portal de demostración: ingrese con su código de licencia de prueba.")
    email = datos.email.strip().lower()
    u = db.scalar(select(models.Usuario).where(func.lower(models.Usuario.email) == email))
    error = HTTPException(401, "Correo o contraseña incorrectos")
    if not u or not u.activo:
        raise error
    if u.bloqueado_hasta and u.bloqueado_hasta > datetime.now():
        minutos = int((u.bloqueado_hasta - datetime.now()).total_seconds() // 60) + 1
        raise HTTPException(429, f"Cuenta bloqueada temporalmente por intentos fallidos. Intente en {minutos} min.")
    if not verificar_password(datos.password, u.password_hash):
        u.intentos_fallidos += 1
        if u.intentos_fallidos >= MAX_INTENTOS_LOGIN:
            u.bloqueado_hasta = datetime.now() + timedelta(minutes=MINUTOS_BLOQUEO)
            u.intentos_fallidos = 0
            auditar(db, u.id, "bloqueo_cuenta", "Demasiados intentos fallidos", request)
        db.commit()
        raise error
    u.intentos_fallidos = 0
    u.bloqueado_hasta = None
    auditar(db, u.id, "login", "", request)
    db.commit()
    return {"access_token": crear_token(u), "token_type": "bearer", "usuario": usuario_out(u)}


@router.get("/me")
def me(u: models.Usuario = Depends(usuario_actual)):
    return usuario_out(u)


@router.post("/cambiar-password")
def cambiar_password(datos: CambioPasswordIn, request: Request, u: models.Usuario = Depends(usuario_actual),
                     db: Session = Depends(get_db)):
    if not verificar_password(datos.actual, u.password_hash):
        raise HTTPException(400, "La contraseña actual no es correcta")
    if datos.actual == datos.nueva:
        raise HTTPException(400, "La nueva contraseña debe ser diferente")
    validar_fortaleza(datos.nueva)
    u.password_hash = hash_password(datos.nueva)
    u.debe_cambiar_password = False
    auditar(db, u.id, "cambio_password", "", request)
    db.commit()
    return {"ok": True}


@router.post("/aceptar-tratamiento-datos")
def aceptar_datos(request: Request, u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    u.acepto_tratamiento_datos = datetime.now()
    auditar(db, u.id, "autorizacion_habeas_data", "Aceptó política de tratamiento de datos (Ley 1581/2012)", request)
    db.commit()
    return {"ok": True}


@router.get("/notificaciones")
def notificaciones(u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    items = db.scalars(select(models.Notificacion).where(models.Notificacion.usuario_id == u.id)
                       .order_by(models.Notificacion.fecha.desc()).limit(50)).all()
    return [{"id": n.id, "titulo": n.titulo, "texto": n.texto, "enlace": n.enlace, "leida": n.leida,
             "fecha": n.fecha} for n in items]


@router.post("/notificaciones/leer-todas")
def leer_todas(u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    for n in db.scalars(select(models.Notificacion).where(models.Notificacion.usuario_id == u.id,
                                                          models.Notificacion.leida.is_(False))):
        n.leida = True
    db.commit()
    return {"ok": True}


# ---------- Licencias de prueba (solo servidor de demostración) ----------

@router.post("/licencia")
def ingresar_con_licencia(datos: LicenciaIn, request: Request, db: Session = Depends(get_db)):
    if not MODO_DEMO:
        raise HTTPException(404, "No disponible")
    try:
        lic = licencias.verificar(datos.codigo)
    except licencias.LicenciaInvalida as e:
        raise HTTPException(401, str(e))
    email = licencias.PERFILES.get(datos.perfil)
    if not email:
        raise HTTPException(400, "Perfil no válido")
    u = db.scalar(select(models.Usuario).where(models.Usuario.email == email))
    if not u:
        raise HTTPException(503, "El portal de demostración se está preparando, intente en un minuto")
    auditar(db, u.id, "licencia_prueba", f"{lic['conjunto']} · {datos.perfil} · vence {lic['vence']}", request)
    db.commit()
    token = crear_token(u, hasta=licencias.fin_del_dia(lic["vence"]),
                        extra={"lic": lic["conjunto"], "vence": lic["vence"].isoformat()})
    return {"access_token": token, "token_type": "bearer", "usuario": usuario_out(u),
            "licencia": {"conjunto": lic["conjunto"], "vence": lic["vence"].isoformat(), "perfil": datos.perfil}}


@router.post("/licencia/generar")
def generar_licencia(datos: GenerarLicenciaIn, request: Request):
    if not MODO_DEMO or not CLAVE_MAESTRA:
        raise HTTPException(404, "No disponible")
    if not hmac.compare_digest(datos.clave_maestra.encode(), CLAVE_MAESTRA.encode()):
        raise HTTPException(401, "Clave maestra incorrecta")
    if not datos.conjunto.strip():
        raise HTTPException(400, "Escriba el nombre del conjunto")
    if not 1 <= datos.dias <= 90:
        raise HTTPException(400, "La licencia de prueba puede durar entre 1 y 90 días")
    lic = licencias.generar(datos.conjunto, datos.dias, datos.contacto)
    base = str(request.base_url).rstrip("/")
    lic["enlace"] = f"{base}/?licencia={lic['codigo']}"
    return lic
