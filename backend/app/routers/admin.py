"""Panel de administración: usuarios, unidades, facturación, pagos, importación, cartera e indicadores."""
import secrets
import string
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models
from ..cartera import estado_cuenta, liquidar_intereses, resumen_cartera
from ..db import get_db
from ..notificaciones import notificar
from ..security import auditar, hash_password, requiere_rol

router = APIRouter(prefix="/api/admin", tags=["Administración"])

gestion = requiere_rol(*models.ROLES_GESTION)
solo_admin = requiere_rol("administrador")
lectura = requiere_rol(*models.ROLES_LECTURA_GLOBAL)


def _param(db: Session, clave: str, defecto: str = "") -> str:
    p = db.get(models.Parametro, clave)
    return p.valor if p else defecto


def _clave_temporal() -> str:
    alfabeto = string.ascii_letters + string.digits
    while True:
        c = "".join(secrets.choice(alfabeto) for _ in range(10))
        if any(ch.isdigit() for ch in c) and any(ch.isalpha() for ch in c):
            return c


# ---------------- Usuarios ----------------

class UsuarioIn(BaseModel):
    email: EmailStr
    nombre: str
    rol: str = "propietario"
    documento: str | None = None
    telefono: str | None = None
    unidad_id: int | None = None
    relacion: str = "propietario"


class UsuarioUpdate(BaseModel):
    nombre: str | None = None
    rol: str | None = None
    telefono: str | None = None
    activo: bool | None = None


class AsignacionIn(BaseModel):
    unidad_id: int
    relacion: str = "propietario"


def _usuario_admin_out(u: models.Usuario) -> dict:
    return {"id": u.id, "email": u.email, "nombre": u.nombre, "rol": u.rol, "documento": u.documento,
            "telefono": u.telefono, "activo": u.activo, "creado": u.creado,
            "acepto_tratamiento_datos": u.acepto_tratamiento_datos,
            "unidades": [{"id": uu.unidad_id, "etiqueta": uu.unidad.etiqueta, "relacion": uu.relacion}
                         for uu in u.unidades]}


@router.get("/usuarios")
def listar_usuarios(q: str | None = None, u: models.Usuario = Depends(gestion), db: Session = Depends(get_db)):
    stmt = select(models.Usuario).order_by(models.Usuario.nombre)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(models.Usuario.nombre.ilike(like) | models.Usuario.email.ilike(like))
    return [_usuario_admin_out(x) for x in db.scalars(stmt)]


@router.post("/usuarios")
def crear_usuario(datos: UsuarioIn, request: Request, u: models.Usuario = Depends(solo_admin),
                  db: Session = Depends(get_db)):
    if datos.rol not in models.ROLES:
        raise HTTPException(400, "Rol no válido")
    email = datos.email.lower()
    if db.scalar(select(models.Usuario).where(func.lower(models.Usuario.email) == email)):
        raise HTTPException(409, "Ya existe un usuario con ese correo")
    clave = _clave_temporal()
    nuevo = models.Usuario(email=email, nombre=datos.nombre.strip(), rol=datos.rol, documento=datos.documento,
                           telefono=datos.telefono, password_hash=hash_password(clave), debe_cambiar_password=True)
    db.add(nuevo)
    db.flush()
    if datos.unidad_id:
        if not db.get(models.Unidad, datos.unidad_id):
            raise HTTPException(404, "Unidad no encontrada")
        db.add(models.UsuarioUnidad(usuario_id=nuevo.id, unidad_id=datos.unidad_id, relacion=datos.relacion))
    auditar(db, u.id, "crear_usuario", f"{email} rol={datos.rol}", request)
    db.commit()
    db.refresh(nuevo)
    # La clave temporal se muestra una sola vez al administrador para que la entregue al propietario.
    return {"usuario": _usuario_admin_out(nuevo), "clave_temporal": clave}


@router.patch("/usuarios/{uid}")
def actualizar_usuario(uid: int, datos: UsuarioUpdate, request: Request, u: models.Usuario = Depends(solo_admin),
                       db: Session = Depends(get_db)):
    x = db.get(models.Usuario, uid)
    if not x:
        raise HTTPException(404, "Usuario no encontrado")
    cambios = datos.model_dump(exclude_none=True)
    if "rol" in cambios and cambios["rol"] not in models.ROLES:
        raise HTTPException(400, "Rol no válido")
    if x.id == u.id and (cambios.get("activo") is False or cambios.get("rol", "administrador") != "administrador"):
        raise HTTPException(400, "No puede desactivarse ni quitarse el rol de administrador a sí mismo")
    for k, v in cambios.items():
        setattr(x, k, v)
    auditar(db, u.id, "actualizar_usuario", f"{x.email} {cambios}", request)
    db.commit()
    return _usuario_admin_out(x)


@router.post("/usuarios/{uid}/restablecer-clave")
def restablecer(uid: int, request: Request, u: models.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    x = db.get(models.Usuario, uid)
    if not x:
        raise HTTPException(404, "Usuario no encontrado")
    clave = _clave_temporal()
    x.password_hash = hash_password(clave)
    x.debe_cambiar_password = True
    x.intentos_fallidos = 0
    x.bloqueado_hasta = None
    auditar(db, u.id, "restablecer_clave", x.email, request)
    db.commit()
    return {"clave_temporal": clave}


@router.post("/usuarios/{uid}/unidades")
def asignar_unidad(uid: int, datos: AsignacionIn, request: Request, u: models.Usuario = Depends(solo_admin),
                   db: Session = Depends(get_db)):
    x = db.get(models.Usuario, uid)
    if not x or not db.get(models.Unidad, datos.unidad_id):
        raise HTTPException(404, "Usuario o unidad no encontrados")
    if any(uu.unidad_id == datos.unidad_id for uu in x.unidades):
        raise HTTPException(409, "La unidad ya está asignada a este usuario")
    db.add(models.UsuarioUnidad(usuario_id=uid, unidad_id=datos.unidad_id, relacion=datos.relacion))
    auditar(db, u.id, "asignar_unidad", f"{x.email} -> {datos.unidad_id}", request)
    db.commit()
    db.refresh(x)
    return _usuario_admin_out(x)


@router.delete("/usuarios/{uid}/unidades/{unidad_id}")
def quitar_unidad(uid: int, unidad_id: int, request: Request, u: models.Usuario = Depends(solo_admin),
                  db: Session = Depends(get_db)):
    uu = db.scalar(select(models.UsuarioUnidad).where(models.UsuarioUnidad.usuario_id == uid,
                                                      models.UsuarioUnidad.unidad_id == unidad_id))
    if not uu:
        raise HTTPException(404, "Asignación no encontrada")
    db.delete(uu)
    auditar(db, u.id, "quitar_unidad", f"usuario={uid} unidad={unidad_id}", request)
    db.commit()
    return {"ok": True}


# ---------------- Unidades ----------------

class UnidadIn(BaseModel):
    torre: str
    numero: str
    tipo: str = "apartamento"
    coeficiente: Decimal
    area_m2: Decimal | None = None


@router.get("/unidades")
def listar_unidades(u: models.Usuario = Depends(lectura), db: Session = Depends(get_db)):
    unidades = db.scalars(select(models.Unidad).order_by(models.Unidad.torre, models.Unidad.numero)).all()
    return [{"id": x.id, "torre": x.torre, "numero": x.numero, "etiqueta": x.etiqueta, "tipo": x.tipo,
             "coeficiente": x.coeficiente, "area_m2": x.area_m2,
             "usuarios": [{"id": uu.usuario_id, "nombre": uu.usuario.nombre, "relacion": uu.relacion}
                          for uu in x.usuarios]} for x in unidades]


@router.post("/unidades")
def crear_unidad(datos: UnidadIn, request: Request, u: models.Usuario = Depends(solo_admin),
                 db: Session = Depends(get_db)):
    if db.scalar(select(models.Unidad).where(models.Unidad.torre == datos.torre,
                                             models.Unidad.numero == datos.numero)):
        raise HTTPException(409, "La unidad ya existe")
    x = models.Unidad(**datos.model_dump())
    db.add(x)
    auditar(db, u.id, "crear_unidad", x.etiqueta, request)
    db.commit()
    return {"id": x.id}


# ---------------- Cargos y pagos ----------------

class CargoIn(BaseModel):
    unidad_id: int
    periodo: str
    tipo: str
    concepto: str
    valor: Decimal
    fecha_vencimiento: date


class PagoIn(BaseModel):
    unidad_id: int
    fecha: date
    valor: Decimal
    medio: str = "consignacion"
    referencia: str | None = None
    observacion: str | None = None


def _validar_periodo(periodo: str):
    try:
        datetime.strptime(periodo, "%Y-%m")
    except ValueError:
        raise HTTPException(400, "El periodo debe tener formato AAAA-MM")


@router.post("/cargos")
def crear_cargo(datos: CargoIn, request: Request, u: models.Usuario = Depends(gestion),
                db: Session = Depends(get_db)):
    _validar_periodo(datos.periodo)
    if datos.tipo not in models.TIPOS_CARGO:
        raise HTTPException(400, "Tipo de cargo no válido")
    if datos.valor <= 0:
        raise HTTPException(400, "El valor debe ser positivo")
    unidad = db.get(models.Unidad, datos.unidad_id)
    if not unidad:
        raise HTTPException(404, "Unidad no encontrada")
    c = models.Cargo(**datos.model_dump(), creado_por=u.id)
    db.add(c)
    if datos.tipo == "multa":
        for uu in unidad.usuarios:
            notificar(db, uu.usuario, "Se registró una multa en su estado de cuenta",
                      f"{datos.concepto}: ${datos.valor:,.0f}", "/estado-cuenta")
    auditar(db, u.id, "crear_cargo", f"{unidad.etiqueta} {datos.tipo} {datos.valor}", request)
    db.commit()
    return {"id": c.id}


@router.delete("/cargos/{cid}")
def anular_cargo(cid: int, request: Request, u: models.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    c = db.get(models.Cargo, cid)
    if not c:
        raise HTTPException(404, "Cargo no encontrado")
    auditar(db, u.id, "anular_cargo", f"id={c.id} unidad={c.unidad_id} {c.concepto} {c.valor}", request)
    db.delete(c)
    db.commit()
    return {"ok": True}


@router.post("/pagos")
def registrar_pago(datos: PagoIn, request: Request, u: models.Usuario = Depends(gestion),
                   db: Session = Depends(get_db)):
    if datos.valor <= 0:
        raise HTTPException(400, "El valor debe ser positivo")
    unidad = db.get(models.Unidad, datos.unidad_id)
    if not unidad:
        raise HTTPException(404, "Unidad no encontrada")
    if datos.referencia and db.scalar(select(models.Pago).where(models.Pago.referencia == datos.referencia,
                                                                models.Pago.unidad_id == datos.unidad_id)):
        raise HTTPException(409, "Ya existe un pago con esa referencia para la unidad")
    p = models.Pago(**datos.model_dump(), creado_por=u.id)
    db.add(p)
    for uu in unidad.usuarios:
        notificar(db, uu.usuario, "Pago aplicado", f"Se registró su pago de ${datos.valor:,.0f} del "
                  f"{datos.fecha:%d/%m/%Y} en {unidad.etiqueta}.", "/estado-cuenta")
    auditar(db, u.id, "registrar_pago", f"{unidad.etiqueta} {datos.valor} ref={datos.referencia}", request)
    db.commit()
    return {"id": p.id}


@router.get("/unidades/{unidad_id}/movimientos")
def movimientos_unidad(unidad_id: int, u: models.Usuario = Depends(lectura), db: Session = Depends(get_db)):
    unidad = db.get(models.Unidad, unidad_id)
    if not unidad:
        raise HTTPException(404, "Unidad no encontrada")
    ec = estado_cuenta(db, unidad_id)
    ec["unidad"] = unidad.etiqueta
    return ec


# ---------------- Facturación mensual ----------------

class FacturarIn(BaseModel):
    periodo: str
    presupuesto_mensual: Decimal | None = None  # si no viene, se usa el parámetro
    dia_vencimiento: int | None = None


@router.post("/facturar")
def facturar_periodo(datos: FacturarIn, request: Request, u: models.Usuario = Depends(gestion),
                     db: Session = Depends(get_db)):
    """Genera la cuota de administración de cada unidad = presupuesto mensual × coeficiente (art. 29 Ley 675)."""
    _validar_periodo(datos.periodo)
    total = datos.presupuesto_mensual or Decimal(_param(db, "presupuesto_mensual", "0"))
    if total <= 0:
        raise HTTPException(400, "Configure el presupuesto mensual de cuotas en Parámetros")
    dia = datos.dia_vencimiento or int(_param(db, "dia_vencimiento", "10"))
    anio, mes = map(int, datos.periodo.split("-"))
    venc = date(anio, mes, min(dia, 28))
    creados, omitidos = 0, 0
    for unidad in db.scalars(select(models.Unidad)).all():
        existe = db.scalar(select(models.Cargo).where(models.Cargo.unidad_id == unidad.id,
                                                      models.Cargo.periodo == datos.periodo,
                                                      models.Cargo.tipo == "administracion"))
        if existe:
            omitidos += 1
            continue
        valor = (total * Decimal(str(unidad.coeficiente)) / 100).quantize(Decimal("100"), ROUND_HALF_UP)
        db.add(models.Cargo(unidad_id=unidad.id, periodo=datos.periodo, tipo="administracion",
                            concepto=f"Cuota de administración {datos.periodo}", valor=valor,
                            fecha_vencimiento=venc, creado_por=u.id))
        creados += 1
    auditar(db, u.id, "facturar_periodo", f"{datos.periodo} total={total} creados={creados}", request)
    db.commit()
    return {"creados": creados, "omitidos_ya_facturados": omitidos, "vencimiento": venc}


class InteresesIn(BaseModel):
    periodo: str
    fecha_corte: date
    tasa_mensual_pct: Decimal | None = None


@router.post("/liquidar-intereses")
def liquidar(datos: InteresesIn, request: Request, u: models.Usuario = Depends(gestion),
             db: Session = Depends(get_db)):
    _validar_periodo(datos.periodo)
    tasa = datos.tasa_mensual_pct or Decimal(_param(db, "tasa_mora_mensual", "0"))
    tope = Decimal(_param(db, "tope_mora_mensual", "0"))
    if tasa <= 0:
        raise HTTPException(400, "Configure la tasa de mora mensual en Parámetros")
    if tope > 0 and tasa > tope:
        raise HTTPException(400, f"La tasa {tasa}% supera el tope legal configurado ({tope}% mensual). "
                                 "Art. 30 Ley 675 de 2001: máximo 1,5 veces el interés bancario corriente.")
    creados = liquidar_intereses(db, datos.periodo, tasa, datos.fecha_corte, u.id)
    total = sum((Decimal(str(c.valor)) for c in creados), Decimal(0))
    auditar(db, u.id, "liquidar_intereses", f"{datos.periodo} tasa={tasa} unidades={len(creados)} total={total}",
            request)
    db.commit()
    return {"unidades": len(creados), "total_intereses": total, "tasa": tasa}


# ---------------- Importación desde Excel ----------------

COLUMNAS = {
    "cargos": ["torre", "numero", "periodo", "tipo", "concepto", "valor", "fecha_vencimiento"],
    "pagos": ["torre", "numero", "fecha", "valor", "medio", "referencia"],
}


def _parse_valor(crudo) -> Decimal:
    """Acepta 285000, 285000.50, $285.000 y 285.000,50 (formato colombiano)."""
    s = str(crudo).replace("$", "").replace(" ", "").strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1 or (s.count(".") == 1 and len(s.split(".")[1]) == 3):
        s = s.replace(".", "")
    v = Decimal(s)
    if v <= 0:
        raise ValueError("valor no positivo")
    return v


@router.get("/plantilla/{tipo}.xlsx")
def plantilla(tipo: str, u: models.Usuario = Depends(gestion)):
    if tipo not in COLUMNAS:
        raise HTTPException(404, "Plantilla no existe")
    ejemplo = {
        "cargos": [["1", "101", "2026-10", "administracion", "Cuota administración octubre", 285000, "2026-10-10"]],
        "pagos": [["1", "101", "2026-10-05", 285000, "consignacion", "BCO-123456"]],
    }[tipo]
    buf = BytesIO()
    pd.DataFrame(ejemplo, columns=COLUMNAS[tipo]).to_excel(buf, index=False, sheet_name=tipo)
    return Response(buf.getvalue(),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="plantilla_{tipo}.xlsx"'})


@router.post("/importar")
async def importar(request: Request, tipo: str = Form(...), confirmar: bool = Form(False),
                   archivo: UploadFile = File(...), u: models.Usuario = Depends(gestion),
                   db: Session = Depends(get_db)):
    """Importa cargos o pagos. Con confirmar=false solo valida y devuelve la vista previa."""
    if tipo not in COLUMNAS:
        raise HTTPException(400, "Tipo debe ser 'cargos' o 'pagos'")
    contenido = await archivo.read()
    try:
        if (archivo.filename or "").lower().endswith(".csv"):
            df = pd.read_csv(BytesIO(contenido), dtype=str)
        else:
            df = pd.read_excel(BytesIO(contenido), dtype=str)
    except Exception:
        raise HTTPException(400, "No se pudo leer el archivo. Use la plantilla .xlsx")
    df.columns = [str(c).strip().lower() for c in df.columns]
    faltan = [c for c in COLUMNAS[tipo] if c not in df.columns and c not in ("medio", "referencia")]
    if faltan:
        raise HTTPException(400, f"Faltan columnas: {', '.join(faltan)}")
    df = df.fillna("")

    unidades = {(x.torre.strip(), x.numero.strip()): x for x in db.scalars(select(models.Unidad))}
    validas, errores = [], []
    for i, fila in df.iterrows():
        n = i + 2  # fila en Excel
        clave = (str(fila["torre"]).strip(), str(fila["numero"]).strip())
        unidad = unidades.get(clave)
        if not unidad:
            errores.append({"fila": n, "error": f"Unidad T{clave[0]}-{clave[1]} no existe"})
            continue
        try:
            valor = _parse_valor(fila["valor"])
        except Exception:
            errores.append({"fila": n, "error": f"Valor inválido: {fila['valor']}"})
            continue
        try:
            if tipo == "cargos":
                periodo = str(fila["periodo"]).strip()[:7]
                datetime.strptime(periodo, "%Y-%m")
                if fila["tipo"] not in models.TIPOS_CARGO:
                    raise ValueError(f"tipo '{fila['tipo']}' no válido")
                venc = pd.to_datetime(fila["fecha_vencimiento"]).date()
                validas.append(dict(unidad_id=unidad.id, periodo=periodo, tipo=fila["tipo"],
                                    concepto=str(fila["concepto"]).strip() or fila["tipo"], valor=valor,
                                    fecha_vencimiento=venc, _unidad=unidad.etiqueta))
            else:
                fecha = pd.to_datetime(fila["fecha"]).date()
                validas.append(dict(unidad_id=unidad.id, fecha=fecha, valor=valor,
                                    medio=str(fila.get("medio", "")).strip() or "consignacion",
                                    referencia=str(fila.get("referencia", "")).strip() or None,
                                    _unidad=unidad.etiqueta))
        except Exception as e:
            errores.append({"fila": n, "error": f"Dato inválido: {e}"})

    total = sum((v["valor"] for v in validas), Decimal(0))
    if confirmar:
        if errores:
            raise HTTPException(400, "Corrija los errores antes de importar")
        Modelo = models.Cargo if tipo == "cargos" else models.Pago
        for v in validas:
            v.pop("_unidad")
            db.add(Modelo(**v, creado_por=u.id))
        auditar(db, u.id, f"importar_{tipo}", f"{archivo.filename} filas={len(validas)} total={total}", request)
        db.commit()
        return {"importados": len(validas), "total": total}
    return {"vista_previa": validas[:50], "filas_validas": len(validas), "errores": errores, "total": total}


# ---------------- Indicadores ----------------

@router.get("/cartera")
def cartera(hasta: date | None = None, u: models.Usuario = Depends(lectura), db: Session = Depends(get_db)):
    return resumen_cartera(db, hasta)


@router.get("/dashboard")
def dashboard(u: models.Usuario = Depends(lectura), db: Session = Depends(get_db)):
    rc = resumen_cartera(db)
    hoy = date.today()
    sol = db.scalars(select(models.Solicitud)).all()
    abiertas = [s for s in sol if s.estado in ("radicada", "en_tramite")]
    vencidas = [s for s in abiertas if s.fecha_limite < hoy]
    cerradas = [s for s in sol if s.fecha_cierre]
    a_tiempo = [s for s in cerradas if s.fecha_cierre.date() <= s.fecha_limite]
    periodo = hoy.strftime("%Y-%m")
    facturado_mes = db.scalar(select(func.coalesce(func.sum(models.Cargo.valor), 0))
                              .where(models.Cargo.periodo == periodo)) or 0
    recaudo_mes = db.scalar(select(func.coalesce(func.sum(models.Pago.valor), 0))
                            .where(models.Pago.fecha >= hoy.replace(day=1))) or 0
    por_tipo: dict[str, int] = {}
    for s in sol:
        por_tipo[s.tipo] = por_tipo.get(s.tipo, 0) + 1
    vencido_total = sum(v for k, v in rc["totales"].items() if k not in ("al_dia", "saldo"))
    return {
        "cartera": {"saldo_total": rc["totales"].get("saldo", 0), "vencido_total": vencido_total,
                    "edades": {k: rc["totales"].get(k, 0) for k in ("1_30", "31_60", "61_90", "mas_90")},
                    "por_torre": rc["por_torre"], "unidades_morosas": rc["unidades_morosas"],
                    "unidades_total": rc["unidades_total"], "top_morosos": rc["top_morosos"][:5]},
        "mes": {"periodo": periodo, "facturado": facturado_mes, "recaudado": recaudo_mes},
        "solicitudes": {"total": len(sol), "abiertas": len(abiertas), "vencidas": len(vencidas),
                        "cumplimiento_pct": round(len(a_tiempo) / len(cerradas) * 100, 1) if cerradas else None,
                        "por_tipo": por_tipo,
                        "vencidas_detalle": [{"id": s.id, "radicado": s.radicado, "asunto": s.asunto,
                                              "fecha_limite": s.fecha_limite} for s in vencidas[:10]]},
        "usuarios": {"total": db.scalar(select(func.count()).select_from(models.Usuario)),
                     "sin_autorizacion_datos": db.scalar(select(func.count()).select_from(models.Usuario)
                                                         .where(models.Usuario.acepto_tratamiento_datos.is_(None)))},
    }


# ---------------- Parámetros y auditoría ----------------

class ParametroIn(BaseModel):
    valor: str


@router.get("/parametros")
def parametros(u: models.Usuario = Depends(lectura), db: Session = Depends(get_db)):
    return [{"clave": p.clave, "valor": p.valor, "descripcion": p.descripcion}
            for p in db.scalars(select(models.Parametro).order_by(models.Parametro.clave))]


@router.put("/parametros/{clave}")
def actualizar_parametro(clave: str, datos: ParametroIn, request: Request, u: models.Usuario = Depends(solo_admin),
                         db: Session = Depends(get_db)):
    p = db.get(models.Parametro, clave)
    if not p:
        raise HTTPException(404, "Parámetro no existe")
    anterior = p.valor
    p.valor = datos.valor.strip()
    auditar(db, u.id, "actualizar_parametro", f"{clave}: {anterior} -> {p.valor}", request)
    db.commit()
    return {"ok": True}


@router.get("/auditoria")
def auditoria(limite: int = 200, u: models.Usuario = Depends(requiere_rol("administrador", "revisor_fiscal")),
              db: Session = Depends(get_db)):
    filas = db.execute(select(models.Auditoria, models.Usuario.nombre)
                       .join(models.Usuario, models.Usuario.id == models.Auditoria.usuario_id, isouter=True)
                       .order_by(models.Auditoria.fecha.desc()).limit(min(limite, 1000))).all()
    return [{"fecha": a.fecha, "usuario": nombre, "accion": a.accion, "detalle": a.detalle, "ip": a.ip}
            for a, nombre in filas]
