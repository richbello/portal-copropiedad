"""Solicitudes a la administración (PQRS, daños, reservas, certificados, derechos de petición)."""
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models
from ..archivos import guardar_archivo, ruta_absoluta
from ..config import DIAS_RESPUESTA
from ..db import get_db
from ..fechas import dias_habiles_entre, sumar_dias_habiles
from ..notificaciones import notificar
from ..pdfs import pdf_constancia_radicado
from ..security import auditar, unidades_del_usuario, usuario_actual

router = APIRouter(prefix="/api/solicitudes", tags=["Solicitudes"])

ZONAS_COMUNES = ("Salón comunal", "BBQ", "Cancha múltiple", "Piscina", "Gimnasio", "Sala de juntas")


def _es_gestion(u: models.Usuario) -> bool:
    return u.rol in models.ROLES_GESTION


def _puede_ver(u: models.Usuario, s: models.Solicitud) -> bool:
    return u.rol in models.ROLES_LECTURA_GLOBAL or s.usuario_id == u.id or \
        (s.unidad_id is not None and s.unidad_id in unidades_del_usuario(u))


def _semaforo(s: models.Solicitud) -> dict:
    if s.estado in ("respondida", "cerrada"):
        return {"color": "gris", "dias_restantes": None}
    restantes = dias_habiles_entre(date.today(), s.fecha_limite)
    color = "rojo" if restantes < 0 else "amarillo" if restantes <= 2 else "verde"
    return {"color": color, "dias_restantes": restantes}


def solicitud_out(s: models.Solicitud, detalle: bool = False) -> dict:
    out = {
        "id": s.id, "radicado": s.radicado, "tipo": s.tipo, "asunto": s.asunto, "estado": s.estado,
        "fecha_radicado": s.fecha_radicado, "fecha_limite": s.fecha_limite, "fecha_cierre": s.fecha_cierre,
        "solicitante": s.usuario.nombre, "unidad": s.unidad.etiqueta if s.unidad else None,
        "zona_comun": s.zona_comun, "fecha_reserva": s.fecha_reserva, **_semaforo(s),
    }
    if detalle:
        out["descripcion"] = s.descripcion
        out["mensajes"] = [{"id": m.id, "autor": m.usuario.nombre, "rol": m.usuario.rol, "texto": m.texto,
                            "estado_nuevo": m.estado_nuevo, "fecha": m.fecha} for m in s.mensajes]
        out["adjuntos"] = [{"id": a.id, "nombre": a.nombre_original, "fecha": a.fecha} for a in s.adjuntos]
    return out


def _nuevo_radicado(db: Session) -> str:
    anio = date.today().year
    n = db.scalar(select(func.count()).select_from(models.Solicitud)
                  .where(models.Solicitud.radicado.like(f"SOL-{anio}-%"))) or 0
    return f"SOL-{anio}-{n + 1:05d}"


@router.get("/catalogo")
def catalogo():
    return {"tipos": [{"valor": t, "dias_habiles": DIAS_RESPUESTA[t]} for t in models.TIPOS_SOLICITUD],
            "estados": models.ESTADOS_SOLICITUD, "zonas_comunes": ZONAS_COMUNES}


@router.get("")
def listar(estado: str | None = None, tipo: str | None = None, q: str | None = None,
           u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    stmt = select(models.Solicitud).order_by(models.Solicitud.fecha_radicado.desc())
    if u.rol not in models.ROLES_LECTURA_GLOBAL:
        ids = unidades_del_usuario(u)
        stmt = stmt.where((models.Solicitud.usuario_id == u.id) | (models.Solicitud.unidad_id.in_(ids)))
    if estado:
        stmt = stmt.where(models.Solicitud.estado == estado)
    if tipo:
        stmt = stmt.where(models.Solicitud.tipo == tipo)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(models.Solicitud.asunto.ilike(like) | models.Solicitud.radicado.ilike(like))
    return [solicitud_out(s) for s in db.scalars(stmt).all()]


@router.post("")
async def crear(request: Request,
                tipo: str = Form(...), asunto: str = Form(...), descripcion: str = Form(...),
                unidad_id: int | None = Form(None), zona_comun: str | None = Form(None),
                fecha_reserva: date | None = Form(None),
                archivos: list[UploadFile] = File(default=[]),
                u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    if tipo not in models.TIPOS_SOLICITUD:
        raise HTTPException(400, "Tipo de solicitud no válido")
    asunto, descripcion = asunto.strip(), descripcion.strip()
    if len(asunto) < 5 or len(descripcion) < 10:
        raise HTTPException(400, "Describa la solicitud con más detalle (asunto mín. 5 y descripción mín. 10 caracteres)")
    if unidad_id is None and u.unidades:
        unidad_id = u.unidades[0].unidad_id
    if unidad_id is not None and unidad_id not in unidades_del_usuario(u) and not _es_gestion(u):
        raise HTTPException(403, "No puede radicar a nombre de una unidad que no es suya")

    if tipo == "reserva_zona_comun":
        if zona_comun not in ZONAS_COMUNES or not fecha_reserva:
            raise HTTPException(400, "Indique la zona común y la fecha de la reserva")
        if fecha_reserva < date.today():
            raise HTTPException(400, "La fecha de reserva no puede ser pasada")
        choque = db.scalar(select(models.Solicitud).where(
            models.Solicitud.tipo == "reserva_zona_comun", models.Solicitud.zona_comun == zona_comun,
            models.Solicitud.fecha_reserva == fecha_reserva, models.Solicitud.estado != "cerrada"))
        if choque:
            raise HTTPException(409, f"{zona_comun} ya tiene una reserva para el {fecha_reserva:%d/%m/%Y}")

    s = models.Solicitud(radicado=_nuevo_radicado(db), usuario_id=u.id, unidad_id=unidad_id, tipo=tipo,
                         asunto=asunto, descripcion=descripcion,
                         fecha_limite=sumar_dias_habiles(date.today(), DIAS_RESPUESTA[tipo]),
                         zona_comun=zona_comun if tipo == "reserva_zona_comun" else None,
                         fecha_reserva=fecha_reserva if tipo == "reserva_zona_comun" else None)
    db.add(s)
    db.flush()
    for a in archivos:
        if a.filename:
            nombre, ruta = await guardar_archivo(a, f"solicitudes/{s.id}")
            db.add(models.Adjunto(solicitud_id=s.id, nombre_original=nombre, ruta=ruta, subido_por=u.id))

    for gestor in db.scalars(select(models.Usuario).where(models.Usuario.rol == "administrador",
                                                          models.Usuario.activo.is_(True))):
        notificar(db, gestor, f"Nueva solicitud {s.radicado}", f"{u.nombre}: {asunto}", f"/solicitudes/{s.id}")
    auditar(db, u.id, "radicar_solicitud", s.radicado, request)
    db.commit()
    db.refresh(s)
    return solicitud_out(s, detalle=True)


def _obtener(db: Session, sid: int, u: models.Usuario) -> models.Solicitud:
    s = db.get(models.Solicitud, sid)
    if not s:
        raise HTTPException(404, "Solicitud no encontrada")
    if not _puede_ver(u, s):
        raise HTTPException(403, "No tiene acceso a esta solicitud")
    return s


@router.get("/{sid}")
def detalle(sid: int, u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return solicitud_out(_obtener(db, sid, u), detalle=True)


@router.post("/{sid}/mensajes")
async def responder(sid: int, request: Request, texto: str = Form(...), estado: str | None = Form(None),
                    archivos: list[UploadFile] = File(default=[]),
                    u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    s = _obtener(db, sid, u)
    if u.rol in ("consejo", "revisor_fiscal"):
        raise HTTPException(403, "Su rol es de solo consulta")
    if s.estado == "cerrada" and not _es_gestion(u):
        raise HTTPException(400, "La solicitud está cerrada. Radique una nueva si lo requiere.")
    if estado:
        if not _es_gestion(u):
            raise HTTPException(403, "Solo la administración cambia el estado")
        if estado not in models.ESTADOS_SOLICITUD:
            raise HTTPException(400, "Estado no válido")
    texto = texto.strip()
    if not texto:
        raise HTTPException(400, "Escriba un mensaje")

    db.add(models.MensajeSolicitud(solicitud_id=s.id, usuario_id=u.id, texto=texto,
                                   estado_nuevo=estado if estado and estado != s.estado else None))
    if estado and estado != s.estado:
        s.estado = estado
        s.fecha_cierre = datetime.now() if estado in ("respondida", "cerrada") else None
    elif _es_gestion(u) and s.estado == "radicada":
        s.estado = "en_tramite"
    for a in archivos:
        if a.filename:
            nombre, ruta = await guardar_archivo(a, f"solicitudes/{s.id}")
            db.add(models.Adjunto(solicitud_id=s.id, nombre_original=nombre, ruta=ruta, subido_por=u.id))

    if _es_gestion(u):
        notificar(db, s.usuario, f"Respuesta a su solicitud {s.radicado}",
                  f"Estado: {s.estado.replace('_', ' ')}. {texto[:200]}", f"/solicitudes/{s.id}")
    else:
        for gestor in db.scalars(select(models.Usuario).where(models.Usuario.rol == "administrador")):
            notificar(db, gestor, f"Nuevo mensaje en {s.radicado}", texto[:200], f"/solicitudes/{s.id}")
    auditar(db, u.id, "mensaje_solicitud", f"{s.radicado} estado={s.estado}", request)
    db.commit()
    db.refresh(s)
    return solicitud_out(s, detalle=True)


@router.get("/{sid}/adjuntos/{aid}")
def descargar_adjunto(sid: int, aid: int, u: models.Usuario = Depends(usuario_actual),
                      db: Session = Depends(get_db)):
    s = _obtener(db, sid, u)
    a = db.get(models.Adjunto, aid)
    if not a or a.solicitud_id != s.id:
        raise HTTPException(404, "Adjunto no encontrado")
    return FileResponse(ruta_absoluta(a.ruta), filename=a.nombre_original)


@router.get("/{sid}/constancia.pdf")
def constancia(sid: int, u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    s = _obtener(db, sid, u)
    pdf = pdf_constancia_radicado(s, s.unidad.etiqueta if s.unidad else "—")
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="constancia_{s.radicado}.pdf"'})
