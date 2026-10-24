"""Vencimientos de SOAT, revisión técnico-mecánica y vacuna antirrábica, con avisos automáticos.

Cada documento avisa tres veces: 30 días antes, 7 días antes y el día que vence (o al detectarlo
vencido). Cada aviso se envía una sola vez, aunque la revisión corra muchas veces al día.
"""
import logging
import threading
import time
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .db import SessionLocal
from .notificaciones import notificar

log = logging.getLogger("vencimientos")
AVISOS = (30, 7, 0)
NOMBRE_DOC = {"soat": "SOAT", "tecnomecanica": "revisión técnico-mecánica", "vacuna": "vacuna antirrábica"}


def estado(vence: date | None, hoy: date | None = None) -> dict:
    """vigente | por_vencer (30 días o menos) | vencido | sin_dato."""
    if not vence:
        return {"estado": "sin_dato", "dias": None}
    dias = (vence - (hoy or date.today())).days
    return {"estado": "vencido" if dias < 0 else "por_vencer" if dias <= 30 else "vigente", "dias": dias}


def documentos(db: Session, unidad_ids: list[int] | None = None) -> list[dict]:
    """Todos los documentos con fecha de una o varias unidades (o de todas)."""
    filas = []
    vstmt = select(models.Vehiculo).where(models.Vehiculo.tipo.in_(("carro", "moto")))
    mstmt = select(models.Mascota).where(models.Mascota.vacuna_antirrabica_vence.is_not(None))
    if unidad_ids is not None:
        vstmt = vstmt.where(models.Vehiculo.unidad_id.in_(unidad_ids))
        mstmt = mstmt.where(models.Mascota.unidad_id.in_(unidad_ids))
    for v in db.scalars(vstmt):
        nombre = f"{v.tipo} {v.placa or ''}".strip()
        for doc, vence in (("soat", v.soat_vence), ("tecnomecanica", v.tecnomecanica_vence)):
            if vence:
                filas.append({"unidad_id": v.unidad_id, "objeto": f"veh{v.id}", "que": nombre,
                              "documento": doc, "vence": vence, **estado(vence)})
    for m in db.scalars(mstmt):
        filas.append({"unidad_id": m.unidad_id, "objeto": f"mas{m.id}", "que": f"mascota {m.nombre}",
                      "documento": "vacuna", "vence": m.vacuna_antirrabica_vence, **estado(m.vacuna_antirrabica_vence)})
    return sorted(filas, key=lambda f: f["vence"])


def _nivel(dias: int) -> int | None:
    """El aviso más urgente que corresponde hoy (0 = vencido)."""
    for limite in sorted(AVISOS):
        if dias <= limite:
            return limite
    return None


def revisar(db: Session) -> int:
    """Envía los avisos pendientes. Devuelve cuántos se enviaron."""
    enviados = 0
    unidades = {u.id: u for u in db.scalars(select(models.Unidad))}
    for d in documentos(db):
        nivel = _nivel(d["dias"])
        if nivel is None:
            continue
        clave = f"{d['objeto']}:{d['documento']}:{d['vence']}:{nivel}"
        if db.get(models.AlertaEnviada, clave):
            continue
        unidad = unidades.get(d["unidad_id"])
        if not unidad:
            continue
        doc = NOMBRE_DOC[d["documento"]]
        if d["dias"] < 0:
            titulo, texto = f"Venció {doc}: {d['que']}", f"Venció el {d['vence']:%d/%m/%Y}. Renuévelo y actualice la fecha en Mi unidad."
        elif d["dias"] == 0:
            titulo, texto = f"Hoy vence {doc}: {d['que']}", "Renuévelo y actualice la fecha en Mi unidad."
        else:
            titulo, texto = (f"{doc.capitalize()} de {d['que']} vence en {d['dias']} días",
                             f"Vence el {d['vence']:%d/%m/%Y}. Cuando lo renueve, actualice la fecha en Mi unidad.")
        for uu in unidad.usuarios:
            notificar(db, uu.usuario, titulo, texto, "/mi-unidad")
        db.add(models.AlertaEnviada(clave=clave))
        enviados += 1
    db.commit()
    return enviados


def iniciar_revision_periodica(cada_horas: float = 6) -> None:
    """Revisa vencimientos al arrancar el portal y luego cada pocas horas, en segundo plano."""
    def ciclo():
        time.sleep(15)
        while True:
            try:
                with SessionLocal() as db:
                    n = revisar(db)
                if n:
                    log.info("Avisos de vencimiento enviados: %s", n)
            except Exception as e:  # nunca debe tumbar el portal
                log.warning("Error revisando vencimientos: %s", e)
            time.sleep(cada_horas * 3600)
    threading.Thread(target=ciclo, daemon=True, name="vencimientos").start()
