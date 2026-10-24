"""Modelo de datos de la copropiedad."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (Boolean, Date, DateTime, ForeignKey, Integer, Numeric,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

ROLES = ("propietario", "residente", "administrador", "contador", "consejo", "revisor_fiscal")
ROLES_GESTION = ("administrador", "contador")
ROLES_LECTURA_GLOBAL = ("administrador", "contador", "consejo", "revisor_fiscal")

TIPOS_CARGO = ("administracion", "extraordinaria", "multa", "interes_mora", "parqueadero", "otro")
TIPOS_SOLICITUD = ("dano_locativo", "reserva_zona_comun", "certificado", "queja",
                   "derecho_peticion", "solicitud_documentos", "consulta", "otro")
ESTADOS_SOLICITUD = ("radicada", "en_tramite", "respondida", "cerrada")


def ahora() -> datetime:
    return datetime.now()


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(160))
    documento: Mapped[str | None] = mapped_column(String(30))
    telefono: Mapped[str | None] = mapped_column(String(30))
    password_hash: Mapped[str] = mapped_column(String(200))
    rol: Mapped[str] = mapped_column(String(30), default="propietario")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    debe_cambiar_password: Mapped[bool] = mapped_column(Boolean, default=True)
    acepto_tratamiento_datos: Mapped[datetime | None] = mapped_column(DateTime)
    intentos_fallidos: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime)
    creado: Mapped[datetime] = mapped_column(DateTime, default=ahora)

    unidades: Mapped[list["UsuarioUnidad"]] = relationship(back_populates="usuario", cascade="all, delete-orphan")


class Unidad(Base):
    __tablename__ = "unidades"
    __table_args__ = (UniqueConstraint("torre", "numero"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    torre: Mapped[str] = mapped_column(String(20))
    numero: Mapped[str] = mapped_column(String(20))
    tipo: Mapped[str] = mapped_column(String(30), default="apartamento")
    coeficiente: Mapped[Decimal] = mapped_column(Numeric(8, 5), default=0)
    area_m2: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))

    usuarios: Mapped[list["UsuarioUnidad"]] = relationship(back_populates="unidad", cascade="all, delete-orphan")
    cargos: Mapped[list["Cargo"]] = relationship(back_populates="unidad")
    pagos: Mapped[list["Pago"]] = relationship(back_populates="unidad")

    @property
    def etiqueta(self) -> str:
        return f"Torre {self.torre} - {self.numero}"


class UsuarioUnidad(Base):
    """Un propietario puede tener varias unidades y una unidad varios residentes."""
    __tablename__ = "usuario_unidad"
    __table_args__ = (UniqueConstraint("usuario_id", "unidad_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    unidad_id: Mapped[int] = mapped_column(ForeignKey("unidades.id"))
    relacion: Mapped[str] = mapped_column(String(20), default="propietario")  # propietario | residente

    usuario: Mapped[Usuario] = relationship(back_populates="unidades")
    unidad: Mapped[Unidad] = relationship(back_populates="usuarios")


class Cargo(Base):
    __tablename__ = "cargos"
    id: Mapped[int] = mapped_column(primary_key=True)
    unidad_id: Mapped[int] = mapped_column(ForeignKey("unidades.id"), index=True)
    periodo: Mapped[str] = mapped_column(String(7))  # AAAA-MM
    tipo: Mapped[str] = mapped_column(String(30))
    concepto: Mapped[str] = mapped_column(String(200))
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    fecha_vencimiento: Mapped[date] = mapped_column(Date)
    creado: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    creado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))

    unidad: Mapped[Unidad] = relationship(back_populates="cargos")


class Pago(Base):
    __tablename__ = "pagos"
    id: Mapped[int] = mapped_column(primary_key=True)
    unidad_id: Mapped[int] = mapped_column(ForeignKey("unidades.id"), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    medio: Mapped[str] = mapped_column(String(40), default="consignacion")
    referencia: Mapped[str | None] = mapped_column(String(80))
    observacion: Mapped[str | None] = mapped_column(String(300))
    creado: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    creado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))

    unidad: Mapped[Unidad] = relationship(back_populates="pagos")


class Solicitud(Base):
    __tablename__ = "solicitudes"
    id: Mapped[int] = mapped_column(primary_key=True)
    radicado: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    unidad_id: Mapped[int | None] = mapped_column(ForeignKey("unidades.id"))
    tipo: Mapped[str] = mapped_column(String(30))
    asunto: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(20), default="radicada")
    fecha_radicado: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    fecha_limite: Mapped[date] = mapped_column(Date)
    fecha_cierre: Mapped[datetime | None] = mapped_column(DateTime)
    # Para reservas de zonas comunes
    zona_comun: Mapped[str | None] = mapped_column(String(80))
    fecha_reserva: Mapped[date | None] = mapped_column(Date)

    usuario: Mapped[Usuario] = relationship()
    unidad: Mapped[Unidad | None] = relationship()
    mensajes: Mapped[list["MensajeSolicitud"]] = relationship(
        back_populates="solicitud", order_by="MensajeSolicitud.fecha", cascade="all, delete-orphan")
    adjuntos: Mapped[list["Adjunto"]] = relationship(back_populates="solicitud", cascade="all, delete-orphan")


class MensajeSolicitud(Base):
    __tablename__ = "mensajes_solicitud"
    id: Mapped[int] = mapped_column(primary_key=True)
    solicitud_id: Mapped[int] = mapped_column(ForeignKey("solicitudes.id"), index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    texto: Mapped[str] = mapped_column(Text)
    estado_nuevo: Mapped[str | None] = mapped_column(String(20))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)

    solicitud: Mapped[Solicitud] = relationship(back_populates="mensajes")
    usuario: Mapped[Usuario] = relationship()


class Adjunto(Base):
    __tablename__ = "adjuntos"
    id: Mapped[int] = mapped_column(primary_key=True)
    solicitud_id: Mapped[int] = mapped_column(ForeignKey("solicitudes.id"), index=True)
    nombre_original: Mapped[str] = mapped_column(String(200))
    ruta: Mapped[str] = mapped_column(String(300))
    subido_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)

    solicitud: Mapped[Solicitud] = relationship(back_populates="adjuntos")


class Documento(Base):
    """Actas, presupuesto, estados financieros, reglamento, circulares."""
    __tablename__ = "documentos"
    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(200))
    categoria: Mapped[str] = mapped_column(String(40))
    descripcion: Mapped[str | None] = mapped_column(Text)
    nombre_original: Mapped[str] = mapped_column(String(200))
    ruta: Mapped[str] = mapped_column(String(300))
    publicado: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    publicado_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))


class Notificacion(Base):
    __tablename__ = "notificaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    titulo: Mapped[str] = mapped_column(String(200))
    texto: Mapped[str] = mapped_column(Text)
    enlace: Mapped[str | None] = mapped_column(String(200))
    leida: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Parametro(Base):
    """Parámetros financieros: tasa de mora mensual vigente, cuota base, etc."""
    __tablename__ = "parametros"
    clave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str | None] = mapped_column(String(300))


class Auditoria(Base):
    __tablename__ = "auditoria"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    accion: Mapped[str] = mapped_column(String(60))
    detalle: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(String(60))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class RubroPresupuesto(Base):
    """Presupuesto anual aprobado por la asamblea, por rubro."""
    __tablename__ = "rubros_presupuesto"
    __table_args__ = (UniqueConstraint("vigencia", "codigo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    vigencia: Mapped[int] = mapped_column(Integer, index=True)
    codigo: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(160))
    valor_aprobado: Mapped[Decimal] = mapped_column(Numeric(16, 2))

    gastos: Mapped[list["Gasto"]] = relationship(back_populates="rubro")


class Gasto(Base):
    """Ejecución: cada pago que hace la administración, imputado a un rubro."""
    __tablename__ = "gastos"
    id: Mapped[int] = mapped_column(primary_key=True)
    rubro_id: Mapped[int] = mapped_column(ForeignKey("rubros_presupuesto.id"), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    proveedor: Mapped[str] = mapped_column(String(160))
    concepto: Mapped[str] = mapped_column(String(300))
    valor: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    soporte: Mapped[str | None] = mapped_column(String(120))  # No. factura / comprobante
    creado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))

    rubro: Mapped[RubroPresupuesto] = relationship(back_populates="gastos")
