"""Negocios y clasificados entre vecinos: emprendimientos, servicios, ventas, compras y arriendos."""
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import models
from ..archivos import guardar_archivo, ruta_absoluta
from ..db import get_db
from ..notificaciones import notificar
from ..security import auditar, requiere_rol, usuario_actual

router = APIRouter(prefix="/api/clasificados", tags=["Negocios y clasificados"])
solo_admin = requiere_rol("administrador")
MAX_ACTIVOS = 5
MAX_FOTOS = 3
EXT_FOTOS = {".jpg", ".jpeg", ".png"}


def _nombre_publico(u: models.Usuario) -> str:
    """Nombre y la inicial del apellido: suficiente para reconocerse entre vecinos."""
    partes = u.nombre.replace("(", "").split()
    return partes[0] + (f" {partes[1][0]}." if len(partes) > 1 else "")


def _vigente(a: models.Anuncio) -> bool:
    return a.estado == "activo" and a.vence >= date.today()


def _out(a: models.Anuncio, u: models.Usuario) -> dict:
    out = {
        "id": a.id, "categoria": a.categoria, "titulo": a.titulo, "descripcion": a.descripcion,
        "precio": a.precio, "precio_negociable": a.precio_negociable,
        "telefono": a.telefono, "whatsapp": a.whatsapp, "estado": a.estado, "vigente": _vigente(a),
        "publicado_por": _nombre_publico(a.usuario), "torre": a.unidad.torre if a.unidad else None,
        "creado": a.creado, "vence": a.vence, "fotos": [f.id for f in a.fotos],
        "es_mio": a.usuario_id == u.id,
    }
    if a.usuario_id == u.id or u.rol == "administrador":
        out["motivo_retiro"] = a.motivo_retiro
    if u.rol == "administrador":
        out["reportes"] = [{"motivo": r.motivo, "fecha": r.fecha} for r in a.reportes]
        out["unidad"] = a.unidad.etiqueta if a.unidad else None
    return out


def _precio(texto: str | None) -> Decimal | None:
    if not texto or not texto.strip():
        return None
    try:
        v = Decimal(texto.replace("$", "").replace(".", "").replace(",", ".").strip())
    except InvalidOperation:
        raise HTTPException(400, "Precio no válido. Escriba solo números, por ejemplo 150000")
    if v < 0:
        raise HTTPException(400, "El precio no puede ser negativo")
    return v


def _validar(categoria: str, titulo: str, descripcion: str, telefono: str | None):
    if categoria not in models.CATEGORIAS_ANUNCIO:
        raise HTTPException(400, "Categoría no válida")
    if len(titulo.strip()) < 5:
        raise HTTPException(400, "El título debe tener al menos 5 caracteres")
    if len(descripcion.strip()) < 15:
        raise HTTPException(400, "Describa su anuncio con un poco más de detalle")
    if telefono and len("".join(c for c in telefono if c.isdigit())) < 7:
        raise HTTPException(400, "Teléfono no válido")


@router.get("")
def listar(categoria: str | None = None, q: str | None = None, u: models.Usuario = Depends(usuario_actual),
           db: Session = Depends(get_db)):
    stmt = (select(models.Anuncio).where(models.Anuncio.estado == "activo", models.Anuncio.vence >= date.today())
            .order_by(models.Anuncio.creado.desc()))
    if categoria:
        stmt = stmt.where(models.Anuncio.categoria == categoria)
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(models.Anuncio.titulo.ilike(like), models.Anuncio.descripcion.ilike(like)))
    return [_out(a, u) for a in db.scalars(stmt)]


@router.get("/mios")
def mios(u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return [_out(a, u) for a in db.scalars(select(models.Anuncio).where(models.Anuncio.usuario_id == u.id)
                                            .order_by(models.Anuncio.creado.desc()))]


@router.get("/reportados")
def reportados(u: models.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    anuncios = db.scalars(select(models.Anuncio).where(models.Anuncio.reportes.any())
                          .order_by(models.Anuncio.creado.desc())).all()
    return [_out(a, u) for a in anuncios]


@router.post("")
async def publicar(request: Request, categoria: str = Form(...), titulo: str = Form(...),
                   descripcion: str = Form(...), precio: str | None = Form(None),
                   precio_negociable: bool = Form(False), telefono: str | None = Form(None),
                   whatsapp: bool = Form(True), fotos: list[UploadFile] = File(default=[]),
                   u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    if u.rol in ("consejo", "revisor_fiscal", "contador"):
        raise HTTPException(403, "Su rol no publica anuncios")
    _validar(categoria, titulo, descripcion, telefono)
    activos = [a for a in db.scalars(select(models.Anuncio).where(models.Anuncio.usuario_id == u.id)) if _vigente(a)]
    if len(activos) >= MAX_ACTIVOS:
        raise HTTPException(400, f"Puede tener máximo {MAX_ACTIVOS} anuncios activos. Cierre alguno para publicar otro.")
    fotos = [f for f in fotos if f.filename]
    if len(fotos) > MAX_FOTOS:
        raise HTTPException(400, f"Máximo {MAX_FOTOS} fotos por anuncio")
    for f in fotos:
        if Path(f.filename).suffix.lower() not in EXT_FOTOS:
            raise HTTPException(400, "Las fotos deben ser JPG o PNG")
    a = models.Anuncio(usuario_id=u.id, unidad_id=u.unidades[0].unidad_id if u.unidades else None,
                       categoria=categoria, titulo=titulo.strip(), descripcion=descripcion.strip(),
                       precio=_precio(precio), precio_negociable=precio_negociable,
                       telefono=(telefono or u.telefono or "").strip() or None, whatsapp=whatsapp,
                       vence=date.today() + timedelta(days=models.DIAS_VIGENCIA_ANUNCIO[categoria]))
    db.add(a)
    db.flush()
    for f in fotos:
        _, ruta = await guardar_archivo(f, f"clasificados/{a.id}")
        db.add(models.AnuncioFoto(anuncio_id=a.id, ruta=ruta))
    auditar(db, u.id, "publicar_anuncio", f"{categoria}: {a.titulo}", request)
    db.commit()
    db.refresh(a)
    return _out(a, u)


class AnuncioUpdate(BaseModel):
    categoria: str
    titulo: str
    descripcion: str
    precio: str | None = None
    precio_negociable: bool = False
    telefono: str | None = None
    whatsapp: bool = True


def _propio(db: Session, aid: int, u: models.Usuario) -> models.Anuncio:
    a = db.get(models.Anuncio, aid)
    if not a:
        raise HTTPException(404, "Anuncio no encontrado")
    if a.usuario_id != u.id:
        raise HTTPException(403, "Solo quien publicó el anuncio puede modificarlo")
    if a.estado == "retirado":
        raise HTTPException(400, "Este anuncio fue retirado por la administración")
    return a


@router.put("/{aid}")
def editar(aid: int, d: AnuncioUpdate, request: Request, u: models.Usuario = Depends(usuario_actual),
           db: Session = Depends(get_db)):
    a = _propio(db, aid, u)
    _validar(d.categoria, d.titulo, d.descripcion, d.telefono)
    a.categoria, a.titulo, a.descripcion = d.categoria, d.titulo.strip(), d.descripcion.strip()
    a.precio, a.precio_negociable = _precio(d.precio), d.precio_negociable
    a.telefono, a.whatsapp = (d.telefono or "").strip() or None, d.whatsapp
    auditar(db, u.id, "editar_anuncio", a.titulo, request)
    db.commit()
    return _out(a, u)


@router.post("/{aid}/renovar")
def renovar(aid: int, u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    a = _propio(db, aid, u)
    a.estado = "activo"
    a.vence = date.today() + timedelta(days=models.DIAS_VIGENCIA_ANUNCIO[a.categoria])
    db.commit()
    return _out(a, u)


@router.post("/{aid}/cerrar")
def cerrar(aid: int, u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    a = _propio(db, aid, u)
    a.estado = "cerrado"
    db.commit()
    return _out(a, u)


@router.delete("/{aid}")
def borrar(aid: int, request: Request, u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    a = db.get(models.Anuncio, aid)
    if not a:
        raise HTTPException(404, "Anuncio no encontrado")
    if a.usuario_id != u.id and u.rol != "administrador":
        raise HTTPException(403, "No puede borrar este anuncio")
    auditar(db, u.id, "borrar_anuncio", a.titulo, request)
    db.delete(a)
    db.commit()
    return {"ok": True}


class MotivoIn(BaseModel):
    motivo: str


@router.post("/{aid}/reportar")
def reportar(aid: int, d: MotivoIn, request: Request, u: models.Usuario = Depends(usuario_actual),
             db: Session = Depends(get_db)):
    a = db.get(models.Anuncio, aid)
    if not a or a.estado != "activo":
        raise HTTPException(404, "Anuncio no encontrado")
    if a.usuario_id == u.id:
        raise HTTPException(400, "No puede reportar su propio anuncio")
    if len(d.motivo.strip()) < 5:
        raise HTTPException(400, "Cuéntenos brevemente por qué lo reporta")
    if any(r.usuario_id == u.id for r in a.reportes):
        raise HTTPException(409, "Usted ya reportó este anuncio")
    db.add(models.AnuncioReporte(anuncio_id=a.id, usuario_id=u.id, motivo=d.motivo.strip()))
    for admin in db.scalars(select(models.Usuario).where(models.Usuario.rol == "administrador")):
        notificar(db, admin, f"Anuncio reportado: {a.titulo}", d.motivo.strip()[:200], "/clasificados")
    auditar(db, u.id, "reportar_anuncio", a.titulo, request)
    db.commit()
    return {"ok": True}


@router.post("/{aid}/retirar")
def retirar(aid: int, d: MotivoIn, request: Request, u: models.Usuario = Depends(solo_admin),
            db: Session = Depends(get_db)):
    a = db.get(models.Anuncio, aid)
    if not a:
        raise HTTPException(404, "Anuncio no encontrado")
    if len(d.motivo.strip()) < 5:
        raise HTTPException(400, "Indique el motivo; se le informará a quien publicó")
    a.estado, a.motivo_retiro = "retirado", d.motivo.strip()
    notificar(db, a.usuario, f"Su anuncio \"{a.titulo}\" fue retirado",
              f"Motivo: {a.motivo_retiro}. Si tiene dudas, radique una solicitud a la administración.", "/clasificados")
    auditar(db, u.id, "retirar_anuncio", f"{a.titulo}: {a.motivo_retiro}", request)
    db.commit()
    return _out(a, u)


@router.get("/{aid}/fotos/{fid}")
def foto(aid: int, fid: int, u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    f = db.get(models.AnuncioFoto, fid)
    if not f or f.anuncio_id != aid:
        raise HTTPException(404, "Foto no encontrada")
    return FileResponse(ruta_absoluta(f.ruta), content_disposition_type="inline")
