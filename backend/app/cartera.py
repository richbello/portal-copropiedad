"""Cálculos de cartera: estado de cuenta, saldos, edades de mora e intereses."""
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models

CERO = Decimal("0")


def _d(x) -> Decimal:
    return Decimal(str(x or 0))


def estado_cuenta(db: Session, unidad_id: int, hasta: date | None = None) -> dict:
    """Movimientos en orden cronológico con saldo acumulado.

    Los pagos se aplican primero a los cargos más antiguos y, dentro del mismo
    vencimiento, primero a intereses y luego a capital (art. 1653 Código Civil).
    """
    hasta = hasta or date.today()
    cargos = db.scalars(select(models.Cargo).where(models.Cargo.unidad_id == unidad_id)
                        .order_by(models.Cargo.fecha_vencimiento, models.Cargo.id)).all()
    pagos = db.scalars(select(models.Pago).where(models.Pago.unidad_id == unidad_id)
                       .order_by(models.Pago.fecha, models.Pago.id)).all()

    movimientos = []
    for c in cargos:
        movimientos.append({"fecha": c.fecha_vencimiento, "tipo": "cargo", "categoria": c.tipo,
                            "concepto": c.concepto, "periodo": c.periodo, "debito": _d(c.valor),
                            "credito": CERO, "id": c.id})
    for p in pagos:
        movimientos.append({"fecha": p.fecha, "tipo": "pago", "categoria": p.medio,
                            "concepto": f"Pago {p.medio}" + (f" ref. {p.referencia}" if p.referencia else ""),
                            "periodo": p.fecha.strftime("%Y-%m"), "debito": CERO, "credito": _d(p.valor),
                            "id": p.id})
    movimientos.sort(key=lambda m: (m["fecha"], 0 if m["tipo"] == "cargo" else 1, m["id"]))

    saldo = CERO
    for m in movimientos:
        saldo += m["debito"] - m["credito"]
        m["saldo"] = saldo

    total_cargos = sum((_d(c.valor) for c in cargos), CERO)
    total_pagos = sum((_d(p.valor) for p in pagos), CERO)

    # Aplicación de pagos (FIFO) para saber qué queda pendiente y con qué antigüedad
    pendientes = _pendientes_fifo(cargos, total_pagos)
    edades = {"al_dia": CERO, "1_30": CERO, "31_60": CERO, "61_90": CERO, "mas_90": CERO}
    capital_vencido = CERO
    for c, pendiente in pendientes:
        dias = (hasta - c.fecha_vencimiento).days
        if dias <= 0:
            edades["al_dia"] += pendiente
            continue
        if c.tipo != "interes_mora":
            capital_vencido += pendiente
        if dias <= 30:
            edades["1_30"] += pendiente
        elif dias <= 60:
            edades["31_60"] += pendiente
        elif dias <= 90:
            edades["61_90"] += pendiente
        else:
            edades["mas_90"] += pendiente

    return {
        "unidad_id": unidad_id,
        "fecha_corte": hasta,
        "movimientos": movimientos,
        "total_cargos": total_cargos,
        "total_pagos": total_pagos,
        "saldo": total_cargos - total_pagos,
        "capital_vencido": capital_vencido,
        "edades": edades,
        "pendientes": [{"cargo_id": c.id, "concepto": c.concepto, "periodo": c.periodo,
                        "vencimiento": c.fecha_vencimiento, "pendiente": p} for c, p in pendientes],
    }


def _pendientes_fifo(cargos: list[models.Cargo], total_pagos: Decimal) -> list[tuple[models.Cargo, Decimal]]:
    orden = sorted(cargos, key=lambda c: (c.fecha_vencimiento, 0 if c.tipo == "interes_mora" else 1, c.id))
    disponible = total_pagos
    resultado = []
    for c in orden:
        valor = _d(c.valor)
        aplicado = min(valor, disponible)
        disponible -= aplicado
        if valor - aplicado > 0:
            resultado.append((c, valor - aplicado))
    return resultado


def resumen_cartera(db: Session, hasta: date | None = None) -> dict:
    hasta = hasta or date.today()
    unidades = db.scalars(select(models.Unidad).order_by(models.Unidad.torre, models.Unidad.numero)).all()
    filas = []
    totales = defaultdict(lambda: CERO)
    por_torre = defaultdict(lambda: CERO)
    for u in unidades:
        ec = estado_cuenta(db, u.id, hasta)
        vencido = sum((v for k, v in ec["edades"].items() if k != "al_dia"), CERO)
        propietarios = [uu.usuario.nombre for uu in u.usuarios if uu.relacion == "propietario"]
        filas.append({"unidad_id": u.id, "unidad": u.etiqueta, "torre": u.torre,
                      "propietario": ", ".join(propietarios) or "—",
                      "saldo": ec["saldo"], "vencido": vencido, **ec["edades"]})
        for k, v in ec["edades"].items():
            totales[k] += v
        totales["saldo"] += ec["saldo"]
        por_torre[u.torre] += vencido
    morosas = [f for f in filas if f["vencido"] > 0]
    return {
        "fecha_corte": hasta,
        "unidades": filas,
        "totales": dict(totales),
        "por_torre": dict(por_torre),
        "unidades_total": len(filas),
        "unidades_morosas": len(morosas),
        "top_morosos": sorted(morosas, key=lambda f: f["vencido"], reverse=True)[:10],
    }


def liquidar_intereses(db: Session, periodo: str, tasa_mensual_pct: Decimal, fecha_corte: date,
                       usuario_id: int) -> list[models.Cargo]:
    """Genera un cargo de interés de mora por unidad sobre el capital vencido a la fecha de corte.

    No genera duplicados: si ya existe interés para el periodo y la unidad, se omite.
    """
    creados = []
    for u in db.scalars(select(models.Unidad)).all():
        existe = db.scalar(select(models.Cargo).where(
            models.Cargo.unidad_id == u.id, models.Cargo.periodo == periodo,
            models.Cargo.tipo == "interes_mora"))
        if existe:
            continue
        ec = estado_cuenta(db, u.id, fecha_corte)
        base = ec["capital_vencido"]
        if base <= 0:
            continue
        interes = (base * tasa_mensual_pct / Decimal(100)).quantize(Decimal("1"), ROUND_HALF_UP)
        if interes <= 0:
            continue
        c = models.Cargo(unidad_id=u.id, periodo=periodo, tipo="interes_mora",
                         concepto=f"Intereses de mora {periodo} ({tasa_mensual_pct}% sobre ${base:,.0f})",
                         valor=interes, fecha_vencimiento=fecha_corte, creado_por=usuario_id)
        db.add(c)
        creados.append(c)
    return creados
