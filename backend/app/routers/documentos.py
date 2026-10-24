"""Repositorio de documentos y transparencia presupuestal (presupuesto aprobado vs. ejecutado)."""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..archivos import guardar_archivo, ruta_absoluta
from ..db import get_db
from ..notificaciones import notificar
from ..security import auditar, requiere_rol, usuario_actual

router = APIRouter(prefix="/api", tags=["Documentos y transparencia"])

CATEGORIAS = ("manual_convivencia", "acta_asamblea", "acta_consejo", "presupuesto", "estados_financieros",
              "reglamento", "circular", "contrato", "otro")

gestion = requiere_rol(*models.ROLES_GESTION)


@router.get("/documentos")
def listar_documentos(categoria: str | None = None, u: models.Usuario = Depends(usuario_actual),
                      db: Session = Depends(get_db)):
    stmt = select(models.Documento).order_by(models.Documento.publicado.desc())
    if categoria:
        stmt = stmt.where(models.Documento.categoria == categoria)
    return [{"id": d.id, "titulo": d.titulo, "categoria": d.categoria, "descripcion": d.descripcion,
             "nombre_archivo": d.nombre_original, "publicado": d.publicado} for d in db.scalars(stmt)]


@router.get("/manual-convivencia")
def manual(u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Versión vigente (la más reciente) y versiones anteriores del manual de convivencia."""
    docs = db.scalars(select(models.Documento).where(models.Documento.categoria == "manual_convivencia")
                      .order_by(models.Documento.publicado.desc())).all()
    if not docs:
        return {"vigente": None, "anteriores": []}
    f = lambda d: {"id": d.id, "titulo": d.titulo, "descripcion": d.descripcion,  # noqa: E731
                   "nombre_archivo": d.nombre_original, "publicado": d.publicado}
    return {"vigente": f(docs[0]), "anteriores": [f(d) for d in docs[1:]]}


@router.get("/documentos/{did}/ver")
def ver_en_linea(did: int, u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Igual que descargar, pero para mostrarlo dentro de la página (PDF en línea)."""
    d = db.get(models.Documento, did)
    if not d:
        raise HTTPException(404, "Documento no encontrado")
    return FileResponse(ruta_absoluta(d.ruta), filename=d.nombre_original, content_disposition_type="inline")


@router.get("/documentos/categorias")
def categorias():
    return CATEGORIAS


@router.post("/documentos")
async def publicar(request: Request, titulo: str = Form(...), categoria: str = Form(...),
                   descripcion: str | None = Form(None), notificar_todos: bool = Form(False),
                   archivo: UploadFile = File(...),
                   u: models.Usuario = Depends(gestion), db: Session = Depends(get_db)):
    if categoria not in CATEGORIAS:
        raise HTTPException(400, "Categoría no válida")
    nombre, ruta = await guardar_archivo(archivo, "documentos")
    d = models.Documento(titulo=titulo.strip(), categoria=categoria, descripcion=descripcion,
                         nombre_original=nombre, ruta=ruta, publicado_por=u.id)
    db.add(d)
    if notificar_todos:
        for dest in db.scalars(select(models.Usuario).where(models.Usuario.activo.is_(True))):
            if dest.id != u.id:
                notificar(db, dest, f"Nuevo documento: {d.titulo}",
                          f"La administración publicó un documento en la categoría {categoria.replace('_', ' ')}.",
                          "/documentos")
    auditar(db, u.id, "publicar_documento", d.titulo, request)
    db.commit()
    return {"id": d.id}


@router.get("/documentos/{did}/archivo")
def descargar(did: int, u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    d = db.get(models.Documento, did)
    if not d:
        raise HTTPException(404, "Documento no encontrado")
    return FileResponse(ruta_absoluta(d.ruta), filename=d.nombre_original)


@router.delete("/documentos/{did}")
def eliminar(did: int, request: Request, u: models.Usuario = Depends(requiere_rol("administrador")),
             db: Session = Depends(get_db)):
    d = db.get(models.Documento, did)
    if not d:
        raise HTTPException(404, "Documento no encontrado")
    auditar(db, u.id, "eliminar_documento", d.titulo, request)
    db.delete(d)
    db.commit()
    return {"ok": True}


# ---------------- Transparencia presupuestal ----------------

class RubroIn(BaseModel):
    vigencia: int
    codigo: str
    nombre: str
    valor_aprobado: Decimal


class GastoIn(BaseModel):
    rubro_id: int
    fecha: date
    proveedor: str
    concepto: str
    valor: Decimal
    soporte: str | None = None


@router.get("/presupuesto")
def ejecucion(vigencia: int | None = None, u: models.Usuario = Depends(usuario_actual),
              db: Session = Depends(get_db)):
    vigencia = vigencia or date.today().year
    rubros = db.scalars(select(models.RubroPresupuesto).where(models.RubroPresupuesto.vigencia == vigencia)
                        .order_by(models.RubroPresupuesto.codigo)).all()
    hoy = date.today()
    meses = hoy.month if vigencia == hoy.year else 12
    filas, tot_ap, tot_ej = [], Decimal(0), Decimal(0)
    for r in rubros:
        ejecutado = sum((Decimal(str(g.valor)) for g in r.gastos), Decimal(0))
        aprobado = Decimal(str(r.valor_aprobado))
        esperado = aprobado * meses / 12
        pct = float(ejecutado / aprobado * 100) if aprobado else 0.0
        # Rubros de pago único (pólizas, por ejemplo) no generan alerta de ritmo
        alerta = "sobreejecucion" if ejecutado > aprobado else \
            "ritmo_alto" if len(r.gastos) > 1 and esperado and ejecutado > esperado * Decimal("1.15") else None
        filas.append({"id": r.id, "codigo": r.codigo, "nombre": r.nombre, "aprobado": aprobado,
                      "ejecutado": ejecutado, "disponible": aprobado - ejecutado, "porcentaje": round(pct, 1),
                      "esperado_a_la_fecha": esperado.quantize(Decimal("1")), "alerta": alerta})
        tot_ap += aprobado
        tot_ej += ejecutado
    return {"vigencia": vigencia, "meses_transcurridos": meses, "rubros": filas,
            "total_aprobado": tot_ap, "total_ejecutado": tot_ej,
            "porcentaje_total": round(float(tot_ej / tot_ap * 100), 1) if tot_ap else 0.0}


@router.get("/presupuesto/rubros/{rid}/gastos")
def gastos_rubro(rid: int, u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    r = db.get(models.RubroPresupuesto, rid)
    if not r:
        raise HTTPException(404, "Rubro no encontrado")
    return [{"id": g.id, "fecha": g.fecha, "proveedor": g.proveedor, "concepto": g.concepto,
             "valor": g.valor, "soporte": g.soporte} for g in sorted(r.gastos, key=lambda g: g.fecha, reverse=True)]


@router.post("/presupuesto/rubros")
def crear_rubro(datos: RubroIn, request: Request, u: models.Usuario = Depends(gestion),
                db: Session = Depends(get_db)):
    if db.scalar(select(models.RubroPresupuesto).where(models.RubroPresupuesto.vigencia == datos.vigencia,
                                                       models.RubroPresupuesto.codigo == datos.codigo)):
        raise HTTPException(409, "Ya existe ese código de rubro en la vigencia")
    r = models.RubroPresupuesto(**datos.model_dump())
    db.add(r)
    auditar(db, u.id, "crear_rubro", f"{datos.vigencia} {datos.codigo} {datos.nombre}", request)
    db.commit()
    return {"id": r.id}


@router.post("/presupuesto/gastos")
def registrar_gasto(datos: GastoIn, request: Request, u: models.Usuario = Depends(gestion),
                    db: Session = Depends(get_db)):
    if not db.get(models.RubroPresupuesto, datos.rubro_id):
        raise HTTPException(404, "Rubro no encontrado")
    if datos.valor <= 0:
        raise HTTPException(400, "El valor debe ser positivo")
    g = models.Gasto(**datos.model_dump(), creado_por=u.id)
    db.add(g)
    auditar(db, u.id, "registrar_gasto", f"{datos.proveedor} ${datos.valor}", request)
    db.commit()
    return {"id": g.id}
