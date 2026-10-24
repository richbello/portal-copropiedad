"""Generación de PDFs: estado de cuenta, paz y salvo y constancia de radicado."""
import hashlib
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .config import NIT_CONJUNTO, NOMBRE_CONJUNTO, SECRET_KEY

VERDE = colors.HexColor("#1f4d3a")
GRIS = colors.HexColor("#f1f3f2")

_estilos = getSampleStyleSheet()
TITULO = ParagraphStyle("t", parent=_estilos["Title"], textColor=VERDE, fontSize=16, spaceAfter=4)
SUB = ParagraphStyle("s", parent=_estilos["Normal"], fontSize=9, textColor=colors.HexColor("#555555"))
NORMAL = ParagraphStyle("n", parent=_estilos["Normal"], fontSize=10, leading=14)
PEQ = ParagraphStyle("p", parent=_estilos["Normal"], fontSize=7.5, textColor=colors.HexColor("#777777"))


def pesos(v) -> str:
    v = Decimal(str(v or 0))
    signo = "-" if v < 0 else ""
    return f"{signo}${abs(v):,.0f}".replace(",", ".")


def codigo_verificacion(*partes) -> str:
    base = "|".join(str(p) for p in partes) + SECRET_KEY
    return hashlib.sha256(base.encode()).hexdigest()[:12].upper()


def _encabezado(titulo: str) -> list:
    return [Paragraph(NOMBRE_CONJUNTO, TITULO),
            Paragraph(f"NIT {NIT_CONJUNTO} · Propiedad Horizontal (Ley 675 de 2001)", SUB),
            Spacer(1, 0.4 * cm),
            Paragraph(f"<b>{titulo}</b>", ParagraphStyle("h", parent=NORMAL, fontSize=13, textColor=VERDE)),
            Spacer(1, 0.3 * cm)]


def _doc(buf):
    return SimpleDocTemplate(buf, pagesize=letter, leftMargin=2 * cm, rightMargin=2 * cm,
                             topMargin=1.8 * cm, bottomMargin=1.8 * cm)


def pdf_estado_cuenta(unidad_etiqueta: str, propietarios: str, ec: dict) -> bytes:
    buf = BytesIO()
    elems = _encabezado("Estado de cuenta")
    elems.append(Paragraph(f"Unidad: <b>{unidad_etiqueta}</b><br/>Propietario(s): {propietarios}<br/>"
                           f"Fecha de corte: {ec['fecha_corte']:%d/%m/%Y}", NORMAL))
    elems.append(Spacer(1, 0.4 * cm))

    resumen = [["Total cargos", "Total pagos", "Saldo", "Vencido"],
               [pesos(ec["total_cargos"]), pesos(ec["total_pagos"]), pesos(ec["saldo"]),
                pesos(sum(v for k, v in ec["edades"].items() if k != "al_dia"))]]
    t = Table(resumen, colWidths=[4.2 * cm] * 4)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), VERDE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("FONTSIZE", (0, 0), (-1, -1), 9), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                           ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                           ("BOX", (0, 0), (-1, -1), 0.5, VERDE)]))
    elems += [t, Spacer(1, 0.5 * cm)]

    filas = [["Fecha", "Periodo", "Concepto", "Débito", "Crédito", "Saldo"]]
    for m in ec["movimientos"]:
        filas.append([m["fecha"].strftime("%d/%m/%Y"), m["periodo"], Paragraph(m["concepto"], PEQ),
                      pesos(m["debito"]) if m["debito"] else "", pesos(m["credito"]) if m["credito"] else "",
                      pesos(m["saldo"])])
    t = Table(filas, colWidths=[2.1 * cm, 1.7 * cm, 6.4 * cm, 2.4 * cm, 2.4 * cm, 2.4 * cm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), VERDE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("FONTSIZE", (0, 0), (-1, -1), 8), ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
                           ("LINEBELOW", (0, -1), (-1, -1), 0.5, VERDE)]))
    elems.append(t)
    elems.append(Spacer(1, 0.6 * cm))
    cod = codigo_verificacion("EC", unidad_etiqueta, ec["fecha_corte"], ec["saldo"])
    elems.append(Paragraph(f"Documento generado el {datetime.now():%d/%m/%Y %H:%M}. "
                           f"Código de verificación: {cod}", PEQ))
    _doc(buf).build(elems)
    return buf.getvalue()


def pdf_paz_y_salvo(unidad_etiqueta: str, propietarios: str, fecha: date) -> bytes:
    buf = BytesIO()
    elems = _encabezado("Certificado de paz y salvo")
    elems.append(Spacer(1, 0.6 * cm))
    elems.append(Paragraph(
        f"La administración de <b>{NOMBRE_CONJUNTO}</b> certifica que la unidad <b>{unidad_etiqueta}</b>, "
        f"cuyo(s) propietario(s) registrado(s) es (son) <b>{propietarios}</b>, se encuentra a paz y salvo "
        f"por concepto de cuotas de administración ordinarias, extraordinarias, multas e intereses "
        f"a la fecha <b>{fecha:%d/%m/%Y}</b>.", ParagraphStyle("j", parent=NORMAL, alignment=4, leading=16)))
    elems.append(Spacer(1, 0.6 * cm))
    elems.append(Paragraph("Este certificado se expide a solicitud del interesado y tiene validez hasta el "
                           "último día del mes de su expedición.", NORMAL))
    elems.append(Spacer(1, 1.5 * cm))
    elems.append(Paragraph("_______________________________<br/>Administración", NORMAL))
    elems.append(Spacer(1, 1 * cm))
    cod = codigo_verificacion("PYS", unidad_etiqueta, fecha)
    elems.append(Paragraph(f"Código de verificación: {cod}", PEQ))
    _doc(buf).build(elems)
    return buf.getvalue()


def pdf_constancia_radicado(sol, unidad_etiqueta: str) -> bytes:
    buf = BytesIO()
    elems = _encabezado("Constancia de radicación")
    datos = [["Radicado", sol.radicado], ["Fecha de radicación", f"{sol.fecha_radicado:%d/%m/%Y %H:%M}"],
             ["Solicitante", sol.usuario.nombre], ["Unidad", unidad_etiqueta],
             ["Tipo", sol.tipo.replace("_", " ").capitalize()], ["Asunto", sol.asunto],
             ["Fecha límite de respuesta", f"{sol.fecha_limite:%d/%m/%Y}"]]
    t = Table(datos, colWidths=[5 * cm, 11.5 * cm])
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9.5), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                           ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, GRIS]),
                           ("BOX", (0, 0), (-1, -1), 0.5, VERDE)]))
    elems += [t, Spacer(1, 0.5 * cm), Paragraph("<b>Descripción</b>", NORMAL),
              Paragraph(sol.descripcion.replace("\n", "<br/>"), NORMAL), Spacer(1, 0.6 * cm)]
    if sol.tipo == "derecho_peticion":
        elems.append(Paragraph("Petición radicada en los términos del artículo 23 de la Constitución Política "
                               "y la Ley 1755 de 2015.", PEQ))
    cod = codigo_verificacion("RAD", sol.radicado, sol.fecha_radicado)
    elems.append(Paragraph(f"Código de verificación: {cod}", PEQ))
    _doc(buf).build(elems)
    return buf.getvalue()
