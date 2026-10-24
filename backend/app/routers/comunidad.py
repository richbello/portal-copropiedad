"""Comunidad: calendario de eventos, censo de personas y mascotas, vehículos y parqueaderos."""
import csv
import io
import random
import secrets
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..notificaciones import notificar
from ..security import auditar, requiere_rol, unidades_del_usuario, usuario_actual

router = APIRouter(prefix="/api", tags=["Comunidad"])

solo_admin = requiere_rol("administrador")
lectura = requiere_rol(*models.ROLES_LECTURA_GLOBAL)
MESES_VIGENCIA_CENSO = 6


# ======================= Calendario =======================

class EventoIn(BaseModel):
    titulo: str
    descripcion: str | None = None
    categoria: str = "otro"
    lugar: str | None = None
    inicio: datetime
    fin: datetime | None = None
    todo_el_dia: bool = False
    notificar_todos: bool = False

    @field_validator("categoria")
    @classmethod
    def _cat(cls, v):
        if v not in models.CATEGORIAS_EVENTO:
            raise ValueError("categoría no válida")
        return v


def _evento_out(e: models.Evento) -> dict:
    return {"id": e.id, "titulo": e.titulo, "descripcion": e.descripcion, "categoria": e.categoria,
            "lugar": e.lugar, "inicio": e.inicio, "fin": e.fin, "todo_el_dia": e.todo_el_dia}


@router.get("/eventos")
def listar_eventos(desde: date | None = None, hasta: date | None = None,
                   u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    desde = desde or date.today() - timedelta(days=31)
    hasta = hasta or date.today() + timedelta(days=366)
    stmt = (select(models.Evento)
            .where(models.Evento.inicio >= datetime.combine(desde, datetime.min.time()),
                   models.Evento.inicio < datetime.combine(hasta + timedelta(days=1), datetime.min.time()))
            .order_by(models.Evento.inicio))
    return [_evento_out(e) for e in db.scalars(stmt)]


@router.get("/eventos/categorias")
def categorias_evento():
    return models.CATEGORIAS_EVENTO


def _validar_evento(d: EventoIn):
    if len(d.titulo.strip()) < 3:
        raise HTTPException(400, "Escriba un título para el evento")
    if d.fin and d.fin < d.inicio:
        raise HTTPException(400, "La hora de fin no puede ser anterior al inicio")


@router.post("/eventos")
def crear_evento(d: EventoIn, request: Request, u: models.Usuario = Depends(solo_admin),
                 db: Session = Depends(get_db)):
    _validar_evento(d)
    e = models.Evento(**d.model_dump(exclude={"notificar_todos"}), creado_por=u.id)
    e.titulo = e.titulo.strip()
    db.add(e)
    if d.notificar_todos:
        cuando = e.inicio.strftime("%d/%m/%Y") + ("" if e.todo_el_dia else e.inicio.strftime(" a las %I:%M %p"))
        for dest in db.scalars(select(models.Usuario).where(models.Usuario.activo.is_(True))):
            if dest.id != u.id:
                notificar(db, dest, f"Nuevo evento: {e.titulo}",
                          f"{cuando}{' en ' + e.lugar if e.lugar else ''}.", "/calendario")
    auditar(db, u.id, "crear_evento", f"{e.titulo} {e.inicio:%Y-%m-%d}", request)
    db.commit()
    return _evento_out(e)


@router.put("/eventos/{eid}")
def editar_evento(eid: int, d: EventoIn, request: Request, u: models.Usuario = Depends(solo_admin),
                  db: Session = Depends(get_db)):
    e = db.get(models.Evento, eid)
    if not e:
        raise HTTPException(404, "Evento no encontrado")
    _validar_evento(d)
    for k, v in d.model_dump(exclude={"notificar_todos"}).items():
        setattr(e, k, v)
    auditar(db, u.id, "editar_evento", e.titulo, request)
    db.commit()
    return _evento_out(e)


@router.delete("/eventos/{eid}")
def borrar_evento(eid: int, request: Request, u: models.Usuario = Depends(solo_admin),
                  db: Session = Depends(get_db)):
    e = db.get(models.Evento, eid)
    if not e:
        raise HTTPException(404, "Evento no encontrado")
    auditar(db, u.id, "borrar_evento", f"{e.titulo} {e.inicio:%Y-%m-%d}", request)
    db.delete(e)
    db.commit()
    return {"ok": True}


# ======================= Censo de la unidad =======================
# Datos personales: solo los ve la propia unidad y la administración (Ley 1581 de 2012).

def _acceso_censo(u: models.Usuario, unidad_id: int, db: Session) -> models.Unidad:
    unidad = db.get(models.Unidad, unidad_id)
    if not unidad:
        raise HTTPException(404, "Unidad no encontrada")
    if u.rol != "administrador" and unidad_id not in unidades_del_usuario(u):
        raise HTTPException(403, "Solo puede ver y editar el censo de su propia unidad")
    return unidad


def _confirmacion(db: Session, unidad_id: int) -> datetime | None:
    c = db.get(models.CensoUnidad, unidad_id)
    return c.confirmado if c else None


def _vigente(confirmado: datetime | None) -> bool:
    return bool(confirmado and confirmado > datetime.now() - timedelta(days=30 * MESES_VIGENCIA_CENSO))


def _persona_out(p):
    return {"id": p.id, "nombre": p.nombre, "relacion": p.relacion, "documento": p.documento,
            "telefono": p.telefono, "menor_de_edad": p.menor_de_edad, "contacto_emergencia": p.contacto_emergencia}


def _mascota_out(m):
    vencida = bool(m.vacuna_antirrabica_vence and m.vacuna_antirrabica_vence < date.today())
    return {"id": m.id, "nombre": m.nombre, "especie": m.especie, "raza": m.raza, "color": m.color,
            "vacuna_antirrabica_vence": m.vacuna_antirrabica_vence, "vacuna_vencida": vencida,
            "potencialmente_peligrosa": m.potencialmente_peligrosa, "poliza": m.poliza,
            "falta_poliza": m.potencialmente_peligrosa and not m.poliza}


def _vehiculo_out(v):
    return {"id": v.id, "tipo": v.tipo, "placa": v.placa, "marca": v.marca, "color": v.color}


def _parq_out(p: models.Parqueadero):
    return {"id": p.id, "codigo": p.codigo, "tipo": p.tipo, "ubicacion": p.ubicacion, "visitantes": p.visitantes,
            "unidad_id": p.unidad_id, "unidad": p.unidad.etiqueta if p.unidad else None,
            "vehiculo": _vehiculo_out(p.vehiculo) if p.vehiculo else None,
            "asignado_desde": p.asignado_desde, "forma_asignacion": p.forma_asignacion}


@router.get("/censo/unidades/{unidad_id}")
def censo_unidad(unidad_id: int, u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    unidad = _acceso_censo(u, unidad_id, db)
    conf = _confirmacion(db, unidad_id)
    q = lambda M: db.scalars(select(M).where(M.unidad_id == unidad_id).order_by(M.id)).all()  # noqa: E731
    return {
        "unidad_id": unidad.id, "unidad": unidad.etiqueta,
        "personas": [_persona_out(p) for p in q(models.Persona)],
        "mascotas": [_mascota_out(m) for m in q(models.Mascota)],
        "vehiculos": [_vehiculo_out(v) for v in q(models.Vehiculo)],
        "parqueaderos": [_parq_out(p) for p in q(models.Parqueadero)],
        "confirmado": conf, "vigente": _vigente(conf), "meses_vigencia": MESES_VIGENCIA_CENSO,
    }


class PersonaIn(BaseModel):
    nombre: str
    relacion: str = "familiar"
    documento: str | None = None
    telefono: str | None = None
    menor_de_edad: bool = False
    contacto_emergencia: bool = False


class MascotaIn(BaseModel):
    nombre: str
    especie: str = "perro"
    raza: str | None = None
    color: str | None = None
    vacuna_antirrabica_vence: date | None = None
    potencialmente_peligrosa: bool = False
    poliza: str | None = None


class VehiculoIn(BaseModel):
    tipo: str
    placa: str | None = None
    marca: str | None = None
    color: str | None = None


def _validar(tipo: str, d) -> dict:
    datos = d.model_dump()
    for k, v in datos.items():
        if isinstance(v, str):
            datos[k] = v.strip() or None
    if tipo == "personas":
        if not datos["nombre"] or len(datos["nombre"]) < 3:
            raise HTTPException(400, "Escriba el nombre completo")
        if datos["relacion"] not in models.RELACIONES_PERSONA:
            raise HTTPException(400, "Relación no válida")
        if datos["menor_de_edad"]:
            datos["documento"] = None  # no se piden documentos de menores
            datos["telefono"] = None
    elif tipo == "mascotas":
        if not datos["nombre"]:
            raise HTTPException(400, "Escriba el nombre de la mascota")
        if datos["especie"] not in models.ESPECIES:
            raise HTTPException(400, "Especie no válida")
        if datos["especie"] != "perro":
            datos["potencialmente_peligrosa"] = False
    else:
        if datos["tipo"] not in models.TIPOS_VEHICULO:
            raise HTTPException(400, "Tipo de vehículo no válido")
        if datos["placa"]:
            datos["placa"] = datos["placa"].upper().replace(" ", "").replace("-", "")
        if datos["tipo"] != "bicicleta" and not datos["placa"]:
            raise HTTPException(400, "Escriba la placa del vehículo")
    return datos


MODELOS = {"personas": (models.Persona, PersonaIn), "mascotas": (models.Mascota, MascotaIn),
           "vehiculos": (models.Vehiculo, VehiculoIn)}


def _modelo(tipo: str):
    if tipo not in MODELOS:
        raise HTTPException(404, "Tipo no válido")
    return MODELOS[tipo]


# Debe ir antes de la ruta genérica /{tipo}, que si no la captura
@router.post("/censo/unidades/{unidad_id}/confirmar")
def confirmar_censo(unidad_id: int, request: Request, u: models.Usuario = Depends(usuario_actual),
                    db: Session = Depends(get_db)):
    unidad = _acceso_censo(u, unidad_id, db)
    c = db.get(models.CensoUnidad, unidad_id) or models.CensoUnidad(unidad_id=unidad_id)
    c.confirmado, c.confirmado_por = datetime.now(), u.id
    db.add(c)
    auditar(db, u.id, "censo_confirmado", unidad.etiqueta, request)
    db.commit()
    return {"confirmado": c.confirmado}


@router.post("/censo/unidades/{unidad_id}/{tipo}")
async def agregar(unidad_id: int, tipo: str, request: Request, u: models.Usuario = Depends(usuario_actual),
                  db: Session = Depends(get_db)):
    unidad = _acceso_censo(u, unidad_id, db)
    Modelo, Esquema = _modelo(tipo)
    d = Esquema(**(await request.json()))
    obj = Modelo(unidad_id=unidad_id, **_validar(tipo, d))
    db.add(obj)
    auditar(db, u.id, f"censo_agregar_{tipo}", unidad.etiqueta, request)
    db.commit()
    return {"id": obj.id}


@router.put("/censo/unidades/{unidad_id}/{tipo}/{oid}")
async def editar(unidad_id: int, tipo: str, oid: int, request: Request,
                 u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    unidad = _acceso_censo(u, unidad_id, db)
    Modelo, Esquema = _modelo(tipo)
    obj = db.get(Modelo, oid)
    if not obj or obj.unidad_id != unidad_id:
        raise HTTPException(404, "Registro no encontrado")
    for k, v in _validar(tipo, Esquema(**(await request.json()))).items():
        setattr(obj, k, v)
    auditar(db, u.id, f"censo_editar_{tipo}", unidad.etiqueta, request)
    db.commit()
    return {"ok": True}


@router.delete("/censo/unidades/{unidad_id}/{tipo}/{oid}")
def quitar(unidad_id: int, tipo: str, oid: int, request: Request,
           u: models.Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    unidad = _acceso_censo(u, unidad_id, db)
    Modelo, _ = _modelo(tipo)
    obj = db.get(Modelo, oid)
    if not obj or obj.unidad_id != unidad_id:
        raise HTTPException(404, "Registro no encontrado")
    if tipo == "vehiculos":
        for p in db.scalars(select(models.Parqueadero).where(models.Parqueadero.vehiculo_id == oid)):
            p.vehiculo_id = None
    db.delete(obj)
    auditar(db, u.id, f"censo_quitar_{tipo}", unidad.etiqueta, request)
    db.commit()
    return {"ok": True}


# ======================= Censo: vista de la administración =======================

def _filas_censo(db: Session) -> list[dict]:
    unidades = db.scalars(select(models.Unidad)).all()
    personas, mascotas, vehiculos = {}, {}, {}
    for p in db.scalars(select(models.Persona)):
        personas.setdefault(p.unidad_id, []).append(p)
    for m in db.scalars(select(models.Mascota)):
        mascotas.setdefault(m.unidad_id, []).append(m)
    for v in db.scalars(select(models.Vehiculo)):
        vehiculos.setdefault(v.unidad_id, []).append(v)
    conf = {c.unidad_id: c.confirmado for c in db.scalars(select(models.CensoUnidad))}
    filas = []
    for un in sorted(unidades, key=lambda x: (int(x.torre) if x.torre.isdigit() else 0, x.torre,
                                              int(x.numero) if x.numero.isdigit() else 0, x.numero)):
        ps, ms, vs = personas.get(un.id, []), mascotas.get(un.id, []), vehiculos.get(un.id, [])
        filas.append({
            "unidad_id": un.id, "unidad": un.etiqueta, "torre": un.torre,
            "personas": len(ps), "menores": sum(p.menor_de_edad for p in ps),
            "perros": sum(m.especie == "perro" for m in ms), "gatos": sum(m.especie == "gato" for m in ms),
            "otras_mascotas": sum(m.especie == "otro" for m in ms),
            "carros": sum(v.tipo == "carro" for v in vs), "motos": sum(v.tipo == "moto" for v in vs),
            "bicicletas": sum(v.tipo == "bicicleta" for v in vs),
            "alertas": ([f"{m.nombre}: sin póliza (PPP)" for m in ms if m.potencialmente_peligrosa and not m.poliza]
                        + [f"{m.nombre}: vacuna vencida" for m in ms
                           if m.vacuna_antirrabica_vence and m.vacuna_antirrabica_vence < date.today()]),
            "confirmado": conf.get(un.id), "vigente": _vigente(conf.get(un.id)),
        })
    return filas


@router.get("/censo/resumen")
def resumen_censo(u: models.Usuario = Depends(lectura), db: Session = Depends(get_db)):
    """Totales sin datos personales: lo puede ver el consejo y el revisor fiscal."""
    filas = _filas_censo(db)
    tot = lambda k: sum(f[k] for f in filas)  # noqa: E731
    return {
        "unidades": len(filas), "unidades_confirmadas": sum(f["vigente"] for f in filas),
        "personas": tot("personas"), "menores": tot("menores"),
        "perros": tot("perros"), "gatos": tot("gatos"), "otras_mascotas": tot("otras_mascotas"),
        "carros": tot("carros"), "motos": tot("motos"), "bicicletas": tot("bicicletas"),
        "alertas_mascotas": sum(len(f["alertas"]) for f in filas),
        "meses_vigencia": MESES_VIGENCIA_CENSO,
    }


@router.get("/censo/unidades")
def censo_por_unidad(u: models.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    return _filas_censo(db)


@router.get("/censo/exportar.csv")
def exportar_censo(request: Request, u: models.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["unidad", "tipo", "nombre", "detalle", "documento_o_placa", "telefono", "observacion"])
    unidades = {x.id: x.etiqueta for x in db.scalars(select(models.Unidad))}
    for p in db.scalars(select(models.Persona).order_by(models.Persona.unidad_id)):
        w.writerow([unidades[p.unidad_id], "persona", p.nombre, p.relacion, p.documento or "", p.telefono or "",
                    ("menor de edad " if p.menor_de_edad else "") + ("contacto de emergencia" if p.contacto_emergencia else "")])
    for m in db.scalars(select(models.Mascota).order_by(models.Mascota.unidad_id)):
        w.writerow([unidades[m.unidad_id], "mascota", m.nombre, f"{m.especie} {m.raza or ''}".strip(), "", "",
                    ("PPP póliza " + (m.poliza or "PENDIENTE") if m.potencialmente_peligrosa else "")
                    + (f" vacuna vence {m.vacuna_antirrabica_vence:%d/%m/%Y}" if m.vacuna_antirrabica_vence else "")])
    for v in db.scalars(select(models.Vehiculo).order_by(models.Vehiculo.unidad_id)):
        w.writerow([unidades[v.unidad_id], v.tipo, f"{v.marca or ''} {v.color or ''}".strip(), "", v.placa or "", "", ""])
    auditar(db, u.id, "exportar_censo", "", request)
    db.commit()
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="censo_{date.today():%Y%m%d}.csv"'})


# ======================= Parqueaderos =======================

class GenerarParqIn(BaseModel):
    tipo: str
    prefijo: str
    desde: int = 1
    cantidad: int
    ubicacion: str | None = None
    visitantes: bool = False


class AsignarIn(BaseModel):
    unidad_id: int
    vehiculo_id: int | None = None


class SorteoIn(BaseModel):
    tipo: str
    confirmar: bool = False


@router.get("/parqueaderos")
def listar_parqueaderos(tipo: str | None = None, u: models.Usuario = Depends(lectura),
                        db: Session = Depends(get_db)):
    stmt = select(models.Parqueadero).order_by(models.Parqueadero.tipo, models.Parqueadero.codigo)
    if tipo:
        stmt = stmt.where(models.Parqueadero.tipo == tipo)
    filas = [_parq_out(p) for p in db.scalars(stmt)]
    resumen = {}
    for t in models.TIPOS_VEHICULO:
        de_tipo = [f for f in filas if f["tipo"] == t and not f["visitantes"]]
        resumen[t] = {"total": len(de_tipo), "asignados": sum(1 for f in de_tipo if f["unidad_id"]),
                      "libres": sum(1 for f in de_tipo if not f["unidad_id"]),
                      "visitantes": sum(1 for f in filas if f["tipo"] == t and f["visitantes"]),
                      "en_espera": len(_lista_espera(db, t))}
    return {"parqueaderos": filas, "resumen": resumen}


@router.post("/parqueaderos/generar")
def generar_parqueaderos(d: GenerarParqIn, request: Request, u: models.Usuario = Depends(solo_admin),
                         db: Session = Depends(get_db)):
    if d.tipo not in models.TIPOS_VEHICULO:
        raise HTTPException(400, "Tipo no válido")
    if not 1 <= d.cantidad <= 1000:
        raise HTTPException(400, "Cantidad entre 1 y 1000")
    ancho = max(3, len(str(d.desde + d.cantidad - 1)))
    existentes = set(db.scalars(select(models.Parqueadero.codigo)))
    creados = 0
    for n in range(d.desde, d.desde + d.cantidad):
        codigo = f"{d.prefijo.strip().upper()}-{n:0{ancho}d}"
        if codigo in existentes:
            continue
        db.add(models.Parqueadero(codigo=codigo, tipo=d.tipo, ubicacion=d.ubicacion, visitantes=d.visitantes))
        creados += 1
    auditar(db, u.id, "generar_parqueaderos", f"{d.tipo} {d.prefijo} x{creados}", request)
    db.commit()
    return {"creados": creados, "omitidos_ya_existian": d.cantidad - creados}


@router.put("/parqueaderos/{pid}/asignar")
def asignar(pid: int, d: AsignarIn, request: Request, u: models.Usuario = Depends(solo_admin),
            db: Session = Depends(get_db)):
    p = db.get(models.Parqueadero, pid)
    unidad = db.get(models.Unidad, d.unidad_id)
    if not p or not unidad:
        raise HTTPException(404, "Parqueadero o unidad no encontrados")
    if p.visitantes:
        raise HTTPException(400, "Los parqueaderos de visitantes no se asignan a unidades")
    if p.unidad_id and p.unidad_id != d.unidad_id:
        raise HTTPException(409, f"{p.codigo} ya está asignado a {p.unidad.etiqueta}. Libérelo primero.")
    if d.vehiculo_id:
        v = db.get(models.Vehiculo, d.vehiculo_id)
        if not v or v.unidad_id != d.unidad_id:
            raise HTTPException(400, "El vehículo no pertenece a esa unidad")
        if v.tipo != p.tipo:
            raise HTTPException(400, f"El vehículo es {v.tipo} y el parqueadero es para {p.tipo}")
    p.unidad_id, p.vehiculo_id = d.unidad_id, d.vehiculo_id
    p.asignado_desde, p.forma_asignacion = date.today(), "manual"
    for uu in unidad.usuarios:
        notificar(db, uu.usuario, f"Parqueadero {p.codigo} asignado",
                  f"Se asignó el parqueadero de {p.tipo} {p.codigo} a {unidad.etiqueta}.", "/mi-unidad")
    auditar(db, u.id, "asignar_parqueadero", f"{p.codigo} -> {unidad.etiqueta}", request)
    db.commit()
    return _parq_out(p)


@router.put("/parqueaderos/{pid}/liberar")
def liberar(pid: int, request: Request, u: models.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    p = db.get(models.Parqueadero, pid)
    if not p:
        raise HTTPException(404, "Parqueadero no encontrado")
    anterior = p.unidad.etiqueta if p.unidad else "—"
    p.unidad_id = p.vehiculo_id = p.asignado_desde = p.forma_asignacion = None
    auditar(db, u.id, "liberar_parqueadero", f"{p.codigo} (antes {anterior})", request)
    db.commit()
    return _parq_out(p)


def _lista_espera(db: Session, tipo: str) -> list[dict]:
    """Unidades con vehículo de ese tipo registrado en el censo y sin parqueadero de ese tipo."""
    con_parq = set(db.scalars(select(models.Parqueadero.unidad_id).where(
        models.Parqueadero.tipo == tipo, models.Parqueadero.unidad_id.is_not(None))))
    espera = {}
    for v in db.scalars(select(models.Vehiculo).where(models.Vehiculo.tipo == tipo).order_by(models.Vehiculo.id)):
        if v.unidad_id not in con_parq and v.unidad_id not in espera:
            espera[v.unidad_id] = v
    unidades = {x.id: x.etiqueta for x in db.scalars(select(models.Unidad).where(models.Unidad.id.in_(espera)))}
    return [{"unidad_id": uid, "unidad": unidades[uid], "vehiculo": _vehiculo_out(v)} for uid, v in espera.items()]


@router.get("/parqueaderos/espera/{tipo}")
def lista_espera(tipo: str, u: models.Usuario = Depends(lectura), db: Session = Depends(get_db)):
    if tipo not in models.TIPOS_VEHICULO:
        raise HTTPException(400, "Tipo no válido")
    return _lista_espera(db, tipo)


@router.post("/parqueaderos/sorteo")
def sorteo(d: SorteoIn, request: Request, u: models.Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """Sorteo transparente: cada unidad en espera recibe a lo sumo un parqueadero libre.

    La semilla queda en la auditoría, así cualquiera puede reproducir el resultado.
    Sin confirmar=true solo muestra cuántos participan y cuántos cupos hay.
    """
    if d.tipo not in models.TIPOS_VEHICULO:
        raise HTTPException(400, "Tipo no válido")
    espera = _lista_espera(db, d.tipo)
    libres = db.scalars(select(models.Parqueadero).where(
        models.Parqueadero.tipo == d.tipo, models.Parqueadero.unidad_id.is_(None),
        models.Parqueadero.visitantes.is_(False)).order_by(models.Parqueadero.codigo)).all()
    if not d.confirmar:
        return {"participantes": len(espera), "cupos": len(libres),
                "quedan_en_espera": max(len(espera) - len(libres), 0)}
    if not espera or not libres:
        raise HTTPException(400, "No hay unidades en espera o no hay parqueaderos libres de ese tipo")
    semilla = secrets.token_hex(8)
    rnd = random.Random(semilla)
    orden = [e["unidad_id"] for e in espera]
    rnd.shuffle(orden)
    cupos = list(libres)
    rnd.shuffle(cupos)
    resultado = []
    por_unidad = {e["unidad_id"]: e for e in espera}
    for unidad_id, p in zip(orden, cupos):
        p.unidad_id, p.vehiculo_id = unidad_id, por_unidad[unidad_id]["vehiculo"]["id"]
        p.asignado_desde, p.forma_asignacion = date.today(), "sorteo"
        resultado.append({"unidad": por_unidad[unidad_id]["unidad"], "parqueadero": p.codigo})
        unidad = db.get(models.Unidad, unidad_id)
        for uu in unidad.usuarios:
            notificar(db, uu.usuario, f"Le correspondió el parqueadero {p.codigo}",
                      f"En el sorteo de parqueaderos de {d.tipo} se asignó {p.codigo} a {unidad.etiqueta}.",
                      "/mi-unidad")
    sin_cupo = [por_unidad[x]["unidad"] for x in orden[len(cupos):]]
    auditar(db, u.id, "sorteo_parqueaderos",
            f"tipo={d.tipo} semilla={semilla} participantes={len(espera)} asignados={len(resultado)}", request)
    db.commit()
    return {"semilla": semilla, "asignados": resultado, "sin_cupo": sin_cupo}
