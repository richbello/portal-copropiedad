"""Carga datos de demostración. Uso: python seed.py  (borra y recrea la base de datos)."""
import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app import models
from app.config import DIAS_RESPUESTA, UPLOAD_DIR
from app.db import Base, SessionLocal, engine
from app.fechas import sumar_dias_habiles
from app.security import hash_password

random.seed(7)
CLAVE_DEMO = "Demo2026*"


def pdf_simple(titulo: str, lineas: list[str]) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 720, titulo)
    c.setFont("Helvetica", 11)
    for i, l in enumerate(lineas):
        c.drawString(72, 690 - i * 18, l)
    c.save()
    return buf.getvalue()


def main():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    hoy = date.today()

    params = [
        ("presupuesto_mensual", "7200000", "Total mensual de cuotas a distribuir por coeficiente (presupuesto anual / 12)"),
        ("dia_vencimiento", "10", "Día del mes en que vence la cuota de administración"),
        ("tasa_mora_mensual", "1.9", "Tasa de interés de mora mensual aplicada (%)"),
        ("tope_mora_mensual", "2.0", "Tope legal mensual (%): 1,5 × interés bancario corriente certificado por la Superfinanciera. Actualizar cada mes."),
        ("cuenta_recaudo", "Banco Demo - Cta. Ahorros 000-000000-00 - Convenio 12345", "Cuenta para consignaciones"),
    ]
    for clave, valor, desc in params:
        db.add(models.Parametro(clave=clave, valor=valor, descripcion=desc))

    # 3 torres x 8 apartamentos = 24 unidades. Coeficientes que suman 100%.
    unidades = []
    areas = []
    for torre in ("1", "2", "3"):
        for piso in (1, 2, 3, 4):
            for apto in (1, 2):
                area = Decimal("58.40") if apto == 1 else Decimal("64.20")
                areas.append(area)
                unidades.append(models.Unidad(torre=torre, numero=f"{piso}0{apto}", area_m2=area))
    total_area = sum(areas)
    acumulado = Decimal(0)
    for i, u in enumerate(unidades):
        coef = (u.area_m2 / total_area * 100).quantize(Decimal("0.00001"))
        if i == len(unidades) - 1:
            coef = Decimal(100) - acumulado
        acumulado += coef
        u.coeficiente = coef
        db.add(u)
    db.flush()

    def usuario(email, nombre, rol, **kw):
        x = models.Usuario(email=email, nombre=nombre, rol=rol, password_hash=hash_password(CLAVE_DEMO),
                           debe_cambiar_password=False, acepto_tratamiento_datos=datetime.now(), **kw)
        db.add(x)
        db.flush()
        return x

    admin = usuario("admin@conjunto.co", "Laura Méndez (Administradora)", "administrador")
    usuario("contador@conjunto.co", "Jorge Pineda (Contador)", "contador")
    usuario("consejo@conjunto.co", "Marta Rojas (Consejo)", "consejo")
    usuario("revisor@conjunto.co", "Andrés Gil (Revisor Fiscal)", "revisor_fiscal")

    nombres = ["Carlos Ramírez", "Diana Torres", "Felipe Castro", "Gloria Vargas", "Hernán López",
               "Isabel Moreno", "Julián Herrera", "Karen Suárez", "Luis Ortega", "Mónica Díaz",
               "Néstor Quintero", "Olga Cárdenas", "Pablo Rincón", "Rosa Medina", "Sergio Pardo",
               "Tatiana Rueda", "Víctor Salazar", "Yolanda Prieto", "Andrea Niño", "Bernardo Peña",
               "Camila Acosta", "Daniel Mora", "Elena Fajardo"]
    propietarios = []
    for i, u in enumerate(unidades):
        idx = min(i, len(nombres) - 1)
        if i == len(unidades) - 1:  # el último propietario tiene dos apartamentos
            dueno = propietarios[-1]
        else:
            email = "propietario@conjunto.co" if i == 0 else \
                f"{nombres[idx].split()[0].lower()}.{nombres[idx].split()[1].lower()}@correo.co" \
                .replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
            dueno = usuario(email, nombres[idx], "propietario", telefono=f"3{random.randint(100000000, 299999999)}")
            propietarios.append(dueno)
        db.add(models.UsuarioUnidad(usuario_id=dueno.id, unidad_id=u.id, relacion="propietario"))
    residente = usuario("residente@conjunto.co", "Sofía Ramírez (residente)", "residente")
    db.add(models.UsuarioUnidad(usuario_id=residente.id, unidad_id=unidades[0].id, relacion="residente"))
    db.flush()

    # Facturación de los últimos 6 meses y pagos con distintos comportamientos
    presupuesto = Decimal("7200000")
    perfiles = ["cumplido"] * 15 + ["atrasado"] * 5 + ["moroso"] * 4
    random.shuffle(perfiles)
    perfiles[0] = "atrasado"  # el usuario demo tiene algo de saldo para ver el ejercicio
    meses = []
    for k in range(5, -1, -1):
        y, m = hoy.year, hoy.month - k
        while m <= 0:
            m += 12
            y -= 1
        meses.append((y, m))

    for u, perfil in zip(unidades, perfiles):
        cuota = (presupuesto * u.coeficiente / 100).quantize(Decimal("100"))
        for idx, (y, m) in enumerate(meses):
            periodo = f"{y}-{m:02d}"
            venc = date(y, m, 10)
            db.add(models.Cargo(unidad_id=u.id, periodo=periodo, tipo="administracion",
                                concepto=f"Cuota de administración {periodo}", valor=cuota,
                                fecha_vencimiento=venc, creado_por=admin.id))
            if idx == 3:
                db.add(models.Cargo(unidad_id=u.id, periodo=periodo, tipo="extraordinaria",
                                    concepto="Cuota extraordinaria impermeabilización cubiertas (2/2)",
                                    valor=(Decimal("18000000") * u.coeficiente / 100).quantize(Decimal("100")),
                                    fecha_vencimiento=venc, creado_por=admin.id))
            pagar = (perfil == "cumplido") or (perfil == "atrasado" and idx < 4) or (perfil == "moroso" and idx < 2)
            if pagar and venc <= hoy:
                valor = cuota
                if idx == 3:
                    valor += (Decimal("18000000") * u.coeficiente / 100).quantize(Decimal("100"))
                db.add(models.Pago(unidad_id=u.id, fecha=venc - timedelta(days=random.randint(0, 8)),
                                   valor=valor, medio=random.choice(["consignacion", "transferencia", "pse"]),
                                   referencia=f"REF{u.id:03d}{y}{m:02d}", creado_por=admin.id))
        if perfil == "moroso":
            y, m = meses[-2]
            db.add(models.Cargo(unidad_id=u.id, periodo=f"{y}-{m:02d}", tipo="interes_mora",
                                concepto=f"Intereses de mora {y}-{m:02d} (1.9%)",
                                valor=(cuota * 3 * Decimal("0.019")).quantize(Decimal("1")),
                                fecha_vencimiento=date(y, m, 28), creado_por=admin.id))
    db.add(models.Cargo(unidad_id=unidades[5].id, periodo=f"{hoy:%Y-%m}", tipo="multa",
                        concepto="Multa por ruido fuera de horario (Reglamento art. 48)", valor=Decimal("150000"),
                        fecha_vencimiento=hoy + timedelta(days=15), creado_por=admin.id))

    # Solicitudes
    def solicitud(dueno, unidad, tipo, asunto, descripcion, dias_atras, estado, mensajes=(), **kw):
        f = datetime.now() - timedelta(days=dias_atras)
        n = db.query(models.Solicitud).count() + 1
        s = models.Solicitud(radicado=f"SOL-{f.year}-{n:05d}", usuario_id=dueno.id, unidad_id=unidad.id,
                             tipo=tipo, asunto=asunto, descripcion=descripcion, estado=estado, fecha_radicado=f,
                             fecha_limite=sumar_dias_habiles(f.date(), DIAS_RESPUESTA[tipo]), **kw)
        if estado in ("respondida", "cerrada"):
            s.fecha_cierre = f + timedelta(days=3)
        db.add(s)
        db.flush()
        for i, (autor, texto, est) in enumerate(mensajes):
            db.add(models.MensajeSolicitud(solicitud_id=s.id, usuario_id=autor.id, texto=texto, estado_nuevo=est,
                                           fecha=f + timedelta(days=i + 1)))
        return s

    p0 = propietarios[0]
    solicitud(p0, unidades[0], "dano_locativo", "Filtración en el techo del baño",
              "Desde las lluvias de la semana pasada hay una mancha de humedad en el techo del baño principal. "
              "Creo que viene de la cubierta o del apartamento de arriba.", 9, "respondida",
              [(admin, "Recibido. El técnico de mantenimiento visitará el apartamento el jueves entre 9 y 11 a.m.",
                "en_tramite"),
               (p0, "Perfecto, estaré en casa.", None),
               (admin, "Se revisó la tubería del apto. 201: había un sifón suelto. Ya fue reparado. "
                       "Por favor confirme si la mancha deja de crecer.", "respondida")])
    solicitud(p0, unidades[0], "derecho_peticion", "Solicitud de copia de contratos de vigilancia 2026",
              "En ejercicio del derecho de petición (art. 23 C.P. y Ley 1755 de 2015) solicito copia del contrato "
              "de vigilancia vigente, sus otrosíes y las actas de supervisión de los últimos seis meses.", 4,
              "en_tramite", [(admin, "Su petición fue recibida y está siendo tramitada.", "en_tramite")])
    solicitud(p0, unidades[0], "reserva_zona_comun", "Reserva salón comunal - cumpleaños",
              "Solicito reservar el salón comunal para una reunión familiar de 30 personas de 3 a 8 p.m.", 1,
              "radicada", zona_comun="Salón comunal", fecha_reserva=hoy + timedelta(days=12))
    solicitud(propietarios[3], unidades[3], "queja", "Perros sin traílla en zonas verdes",
              "Varios residentes de la torre 2 sacan sus perros sin traílla y sin recoger los excrementos.", 25,
              "radicada")
    solicitud(propietarios[7], unidades[7], "certificado", "Certificado de residencia para trámite bancario",
              "Necesito un certificado de residencia con mi nombre para un crédito.", 6, "cerrada",
              [(admin, "Adjuntamos el certificado solicitado. Puede retirar el original en portería.", "cerrada")])

    # Presupuesto aprobado y ejecución
    rubros = [("1.01", "Vigilancia y seguridad", 42000000), ("1.02", "Aseo y cafetería", 18600000),
              ("1.03", "Mantenimiento zonas comunes", 9600000), ("1.04", "Servicios públicos áreas comunes", 7800000),
              ("1.05", "Honorarios administración", 6000000), ("1.06", "Honorarios contador y revisor fiscal", 2400000),
              ("1.07", "Póliza de áreas comunes", 1440000), ("1.08", "Fondo de imprevistos (1%)", 864000)]
    proveedores = {"1.01": "Seguridad Andina Ltda.", "1.02": "Limpieza Total S.A.S.", "1.03": "Mantenimientos JR",
                   "1.04": "Enel / Acueducto", "1.05": "Laura Méndez", "1.06": "Contadores Asociados",
                   "1.07": "Aseguradora Demo", "1.08": "—"}
    for cod, nombre, valor in rubros:
        r = models.RubroPresupuesto(vigencia=hoy.year, codigo=cod, nombre=nombre, valor_aprobado=Decimal(valor))
        db.add(r)
        db.flush()
        if cod == "1.08":
            continue
        mensual = Decimal(valor) / 12
        for m in range(1, hoy.month + (0 if hoy.day < 5 else 1)):
            if cod == "1.07" and m != 2:
                continue
            factor = Decimal("1.35") if cod == "1.03" and m in (6, 7) else Decimal(1)
            v = (Decimal(valor) if cod == "1.07" else mensual * factor).quantize(Decimal("1"))
            db.add(models.Gasto(rubro_id=r.id, fecha=date(hoy.year, m, 5), proveedor=proveedores[cod],
                                concepto=f"{nombre} - {date(hoy.year, m, 1):%m/%Y}", valor=v,
                                soporte=f"FE-{cod.replace('.', '')}{m:02d}", creado_por=admin.id))

    # Documentos
    docs = [("Acta asamblea ordinaria 2026", "acta_asamblea", "Aprobación de presupuesto y elección de consejo",
             ["Asamblea General Ordinaria - marzo 2026", "Quórum: 78,4% de coeficientes", "Presupuesto aprobado."]),
            ("Presupuesto 2026 aprobado", "presupuesto", "Presupuesto de gastos e ingresos vigencia 2026",
             ["Presupuesto anual: $88.704.000", "Cuota mensual promedio: $300.000"]),
            ("Reglamento de propiedad horizontal", "reglamento", None, ["Reglamento interno - versión 2024"]),
            ("Circular: mantenimiento de tanques", "circular", "Corte de agua programado",
             ["Se informa corte de agua el sábado de 8 a.m. a 2 p.m. por lavado de tanques."])]
    carpeta = UPLOAD_DIR / "documentos"
    carpeta.mkdir(parents=True, exist_ok=True)
    for i, (titulo, cat, desc, lineas) in enumerate(docs):
        ruta = f"documentos/demo_{i}.pdf"
        (UPLOAD_DIR / ruta).write_bytes(pdf_simple(titulo, lineas))
        db.add(models.Documento(titulo=titulo, categoria=cat, descripcion=desc,
                                nombre_original=f"{titulo}.pdf", ruta=ruta, publicado_por=admin.id,
                                publicado=datetime.now() - timedelta(days=30 * (len(docs) - i))))

    db.add(models.Notificacion(usuario_id=p0.id, titulo="Bienvenido al portal",
                               texto="Desde aquí puede consultar su estado de cuenta y radicar solicitudes.",
                               enlace="/"))
    db.commit()
    db.close()
    print("Base de datos de demostración creada.")
    print(f"Clave para todos los usuarios demo: {CLAVE_DEMO}")
    print("  admin@conjunto.co · contador@conjunto.co · consejo@conjunto.co · revisor@conjunto.co")
    print("  propietario@conjunto.co · residente@conjunto.co")


if __name__ == "__main__":
    main()
