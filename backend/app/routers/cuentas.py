"""Estado de cuenta, PDF y paz y salvo para el propietario."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models
from ..cartera import estado_cuenta
from ..db import get_db
from ..pdfs import pdf_estado_cuenta, pdf_paz_y_salvo
from ..security import auditar, usuario_actual, verificar_acceso_unidad

router = APIRouter(prefix="/api/unidades", tags=["Estado de cuenta"])


def _unidad(db: Session, unidad_id: int, u: models.Usuario) -> models.Unidad:
    verificar_acceso_unidad(u, unidad_id)
    unidad = db.get(models.Unidad, unidad_id)
    if not unidad:
        raise HTTPException(404, "Unidad no encontrada")
    return unidad


def _propietarios(unidad: models.Unidad) -> str:
    return ", ".join(uu.usuario.nombre for uu in unidad.usuarios if uu.relacion == "propietario") or "—"


@router.get("/{unidad_id}/estado-cuenta")
def ver_estado_cuenta(unidad_id: int, hasta: date | None = None, u: models.Usuario = Depends(usuario_actual),
                      db: Session = Depends(get_db)):
    unidad = _unidad(db, unidad_id, u)
    ec = estado_cuenta(db, unidad_id, hasta)
    ec["unidad"] = unidad.etiqueta
    ec["coeficiente"] = unidad.coeficiente
    ec["propietarios"] = _propietarios(unidad)
    ec["puede_paz_y_salvo"] = ec["saldo"] <= 0
    return ec


@router.get("/{unidad_id}/estado-cuenta.pdf")
def estado_cuenta_pdf(unidad_id: int, request: Request, u: models.Usuario = Depends(usuario_actual),
                      db: Session = Depends(get_db)):
    unidad = _unidad(db, unidad_id, u)
    pdf = pdf_estado_cuenta(unidad.etiqueta, _propietarios(unidad), estado_cuenta(db, unidad_id))
    auditar(db, u.id, "descarga_estado_cuenta", unidad.etiqueta, request)
    db.commit()
    nombre = f"estado_cuenta_T{unidad.torre}_{unidad.numero}_{date.today():%Y%m%d}.pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@router.get("/{unidad_id}/paz-y-salvo.pdf")
def paz_y_salvo(unidad_id: int, request: Request, u: models.Usuario = Depends(usuario_actual),
                db: Session = Depends(get_db)):
    unidad = _unidad(db, unidad_id, u)
    ec = estado_cuenta(db, unidad_id)
    if ec["saldo"] > 0:
        raise HTTPException(400, f"La unidad tiene saldo pendiente de ${ec['saldo']:,.0f}. "
                                 "No es posible expedir paz y salvo.")
    pdf = pdf_paz_y_salvo(unidad.etiqueta, _propietarios(unidad), date.today())
    auditar(db, u.id, "expedicion_paz_y_salvo", unidad.etiqueta, request)
    db.commit()
    nombre = f"paz_y_salvo_T{unidad.torre}_{unidad.numero}_{date.today():%Y%m%d}.pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
