"""Datos de demostración de comunidad: eventos, censo, parqueaderos y manual de convivencia."""
import random
from datetime import date, datetime, time, timedelta
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from sqlalchemy import select

from app import models
from app.config import NOMBRE_CONJUNTO, UPLOAD_DIR

MANUAL = [
    ("Capítulo 1. Objeto y alcance",
     ["Este manual establece las normas básicas de convivencia para todos los propietarios, residentes, "
      "arrendatarios, visitantes y trabajadores del conjunto. Complementa el reglamento de propiedad "
      "horizontal y la Ley 675 de 2001, y se aplica en armonía con el Código Nacional de Seguridad y "
      "Convivencia Ciudadana (Ley 1801 de 2016)."]),
    ("Capítulo 2. Ruido y horarios",
     ["Entre las 10:00 p.m. y las 7:00 a.m. de domingo a jueves, y entre las 12:00 a.m. y las 8:00 a.m. "
      "los viernes, sábados y festivos, el volumen de música, televisores y reuniones no debe trascender "
      "a las unidades vecinas.",
      "Las obras y reparaciones locativas se permiten de lunes a viernes de 8:00 a.m. a 5:00 p.m. y los "
      "sábados de 9:00 a.m. a 1:00 p.m., previa información a la administración."]),
    ("Capítulo 3. Mascotas",
     ["Toda mascota debe estar registrada en el censo del portal. En zonas comunes los perros deben ir con "
      "traílla y su tenedor debe recoger los excrementos.",
      "Los perros de razas potencialmente peligrosas deben circular con bozal y traílla, y su propietario "
      "debe tener vigente la póliza de responsabilidad civil exigida por la ley.",
      "La vacuna antirrábica debe mantenerse al día; la administración podrá solicitar el carné."]),
    ("Capítulo 4. Parqueaderos",
     ["Los parqueaderos comunales se asignan por sorteo entre las unidades que tengan el vehículo registrado "
      "en el censo. Cada asignación es personal e intransferible y se revisa periódicamente.",
      "La velocidad máxima dentro del conjunto es de 10 km/h. Está prohibido usar los parqueaderos como "
      "bodega o lavar vehículos en ellos.",
      "Las bicicletas deben guardarse en el bicicletero asignado con candado propio."]),
    ("Capítulo 5. Zonas comunes",
     ["El salón comunal, la zona BBQ y demás espacios se reservan a través del portal con al menos tres "
      "días hábiles de anticipación. Quien reserva responde por el aseo y por los daños causados.",
      "Los menores de 12 años deben estar acompañados de un adulto en la piscina y el gimnasio."]),
    ("Capítulo 6. Residuos y reciclaje",
     ["Los residuos se separan en la fuente: blanca para aprovechables, negra para no aprovechables y verde "
      "para orgánicos. Las bolsas se depositan en el cuarto de basuras de la torre en los horarios fijados."]),
    ("Capítulo 7. Procedimiento ante incumplimientos",
     ["Las quejas se radican por el portal. La administración escucha a las partes y, si persiste la falta, "
      "el consejo de administración aplica las sanciones previstas en el reglamento, respetando el debido "
      "proceso y el derecho de defensa (art. 59 y 60 de la Ley 675 de 2001)."]),
]


def pdf_manual() -> bytes:
    buf = BytesIO()
    est = getSampleStyleSheet()
    titulo = ParagraphStyle("t", parent=est["Title"], fontSize=18, textColor="#1f4d3a")
    h = ParagraphStyle("h", parent=est["Heading2"], textColor="#1f4d3a", spaceBefore=14)
    n = ParagraphStyle("n", parent=est["Normal"], fontSize=10.5, leading=15, alignment=4, spaceAfter=6)
    elems = [Paragraph(NOMBRE_CONJUNTO, titulo), Paragraph("Manual de convivencia", est["Heading1"]),
             Paragraph("Documento de demostración. Reemplácelo por el manual aprobado por la asamblea.", n),
             Spacer(1, 0.4 * cm)]
    for cap, parrafos in MANUAL:
        elems.append(Paragraph(cap, h))
        elems += [Paragraph(p, n) for p in parrafos]
    SimpleDocTemplate(buf, pagesize=letter, leftMargin=2.2 * cm, rightMargin=2.2 * cm).build(elems)
    return buf.getvalue()


def cargar(db, admin, unidades, propietarios):
    rnd = random.Random(11)
    hoy = date.today()

    def dia(delta, h=None, m=0):
        d = hoy + timedelta(days=delta)
        return datetime.combine(d, time(h, m)) if h is not None else datetime.combine(d, time(0, 0))

    eventos = [
        ("Asamblea general extraordinaria", "asamblea", "Salón comunal", dia(18, 9), dia(18, 13), False,
         "Orden del día: informe de obras de impermeabilización y aprobación de proveedor de vigilancia. "
         "Si no puede asistir, envíe poder firmado a la administración."),
        ("Lavado de tanques de agua", "corte_servicio", "Todas las torres", dia(6, 8), dia(6, 14), False,
         "Habrá suspensión del servicio de agua. Recomendamos almacenar agua el día anterior."),
        ("Jornada de vacunación de mascotas", "salud", "Zona verde torre 3", dia(9, 9), dia(9, 12), False,
         "Vacuna antirrábica gratuita con la Secretaría de Salud. Traiga el carné de vacunación."),
        ("Novena de aguinaldos", "cultural", "Plazoleta central", dia(40, 18, 30), None, False,
         "Cada torre organiza una noche. Habrá natilla y buñuelos."),
        ("Reunión del consejo de administración", "reunion_consejo", "Oficina de administración",
         dia(3, 19), dia(3, 21), False, None),
        ("Torneo de microfútbol por torres", "deportivo", "Cancha múltiple", dia(13, 8), None, True,
         "Inscripciones en portería hasta el viernes anterior."),
        ("Mantenimiento de ascensores torre 2", "mantenimiento", "Torre 2", dia(-4, 8), dia(-4, 16), False, None),
    ]
    for t, cat, lugar, ini, fin, todo, desc in eventos:
        db.add(models.Evento(titulo=t, categoria=cat, lugar=lugar, inicio=ini, fin=fin, todo_el_dia=todo,
                             descripcion=desc, creado_por=admin.id))

    # Parqueaderos: 12 de carro, 6 de moto, 16 de bicicleta y 3 de visitantes
    parqs = []
    for i in range(1, 13):
        parqs.append(models.Parqueadero(codigo=f"C-{i:03d}", tipo="carro", ubicacion="Sótano"))
    for i in range(1, 4):
        parqs.append(models.Parqueadero(codigo=f"V-{i:03d}", tipo="carro", ubicacion="Entrada", visitantes=True))
    for i in range(1, 7):
        parqs.append(models.Parqueadero(codigo=f"M-{i:03d}", tipo="moto", ubicacion="Sótano"))
    for i in range(1, 17):
        parqs.append(models.Parqueadero(codigo=f"B-{i:03d}", tipo="bicicleta", ubicacion="Bicicletero torre 1"))
    db.add_all(parqs)
    db.flush()

    # Censo de casi todas las unidades
    apellidos = ["Ramírez", "Torres", "Castro", "Vargas", "López", "Moreno", "Herrera", "Suárez"]
    nombres = ["Laura", "Mateo", "Sofía", "Juan", "Valentina", "Samuel", "Daniela", "Tomás", "Isabella", "Martín"]
    razas = [("perro", "Criollo"), ("perro", "Labrador"), ("gato", "Criollo"), ("perro", "French poodle"),
             ("perro", "Pitbull terrier"), ("gato", "Siamés")]
    marcas_carro = ["Renault Logan", "Chevrolet Onix", "Mazda 2", "Kia Picanto", "Toyota Corolla"]
    marcas_moto = ["Yamaha NMAX", "AKT 125", "Suzuki Gixxer", "Honda CB 160"]
    letras = "ABCDEFGHJKLMNPRSTUVWXYZ"
    vehiculos_carro, i_placa = [], 0
    for idx, (u, dueno) in enumerate(zip(unidades, propietarios + [propietarios[-1]])):
        if idx in (7, 15):  # dos unidades aún sin censo, para ver las alertas
            continue
        db.add(models.Persona(unidad_id=u.id, nombre=dueno.nombre, relacion="propietario",
                              telefono=dueno.telefono, contacto_emergencia=True))
        ap = dueno.nombre.split()[-1]
        for _ in range(rnd.randint(0, 3)):
            menor = rnd.random() < 0.5
            db.add(models.Persona(unidad_id=u.id, nombre=f"{rnd.choice(nombres)} {ap}",
                                  relacion="familiar", menor_de_edad=menor))
        if rnd.random() < 0.45:
            esp, raza = rnd.choice(razas)
            ppp = raza == "Pitbull terrier"
            db.add(models.Mascota(unidad_id=u.id, nombre=rnd.choice(["Luna", "Max", "Toby", "Nala", "Rocky", "Milo"]),
                                  especie=esp, raza=raza, potencialmente_peligrosa=ppp,
                                  poliza=None if ppp and idx % 2 else ("POL-2026-" + str(1000 + idx) if ppp else None),
                                  vacuna_antirrabica_vence=hoy + timedelta(days=rnd.randint(-40, 300))))
        i_placa += 1
        if rnd.random() < 0.65:
            placa = f"{letras[i_placa % 23]}{letras[(i_placa * 7) % 23]}{letras[(i_placa * 3) % 23]}{100 + idx * 13 % 900}"
            v = models.Vehiculo(unidad_id=u.id, tipo="carro", placa=placa, marca=rnd.choice(marcas_carro),
                                color=rnd.choice(["Gris", "Blanco", "Rojo", "Negro"]),
                                soat_vence=hoy + timedelta(days=rnd.choice([-12, 5, 20, 90, 200, 300])),
                                tecnomecanica_vence=rnd.choice([None, hoy + timedelta(days=rnd.randint(-20, 330))]))
            db.add(v)
            vehiculos_carro.append(v)
        if rnd.random() < 0.3:
            db.add(models.Vehiculo(unidad_id=u.id, tipo="moto", placa=f"{letras[idx % 23]}{letras[(idx + 5) % 23]}"
                                   f"{letras[(idx + 9) % 23]}{10 + idx}{letras[idx % 23]}",
                                   marca=rnd.choice(marcas_moto), color="Negro",
                                   soat_vence=hoy + timedelta(days=rnd.randint(-10, 300)),
                                   tecnomecanica_vence=hoy + timedelta(days=rnd.randint(10, 300))))
        if rnd.random() < 0.5:
            db.add(models.Vehiculo(unidad_id=u.id, tipo="bicicleta", marca="GW", color="Azul"))
        if idx % 5 != 3:
            db.add(models.CensoUnidad(unidad_id=u.id, confirmado=datetime.now() - timedelta(days=rnd.randint(1, 120)),
                                      confirmado_por=dueno.id))
    db.flush()

    # El usuario demo (Torre 1 - 101) tiene el SOAT próximo a vencer, para ver el aviso
    for v in db.scalars(select(models.Vehiculo).where(models.Vehiculo.unidad_id == unidades[0].id,
                                                      models.Vehiculo.tipo == "carro")):
        v.soat_vence, v.tecnomecanica_vence = hoy + timedelta(days=12), hoy + timedelta(days=210)

    # Asignación inicial de 9 de los 12 parqueaderos de carro; el resto queda para el sorteo
    for p, v in zip([x for x in parqs if x.tipo == "carro" and not x.visitantes][:9], vehiculos_carro):
        p.unidad_id, p.vehiculo_id = v.unidad_id, v.id
        p.asignado_desde, p.forma_asignacion = hoy - timedelta(days=200), "sorteo"

    # Negocios y clasificados
    anuncios = [
        (0, "negocio", "Tortas y postres por encargo", "Tortas de cumpleaños, cupcakes y postres en vaso. "
         "Pedidos con dos días de anticipación. Entrego en su apartamento.", 45000, True),
        (2, "servicio", "Clases de matemáticas y física", "Licenciado con experiencia en colegio. Refuerzo para "
         "bachillerato y preparación para el ICFES. Clases en la sala de juntas o virtuales.", 35000, False),
        (4, "venta", "Bicicleta de niño rin 20", "En buen estado, poco uso. Incluye casco. Se puede ver en la torre 2.",
         180000, True),
        (5, "arriendo", "Arriendo parqueadero cubierto", "Parqueadero propio disponible para carro pequeño. "
         "Solo para residentes del conjunto.", 120000, False),
        (8, "compra", "Busco coche para bebé", "Busco coche en buen estado, preferiblemente plegable. Pago justo.",
         None, False),
        (10, "servicio", "Plomería y arreglos locativos", "Destapes, fugas, cambio de grifería y pintura. "
         "Trabajo garantizado y precios de vecino.", None, False),
    ]
    for i, cat, titulo, desc, precio, neg in anuncios:
        dueno = propietarios[i]
        db.add(models.Anuncio(usuario_id=dueno.id, unidad_id=unidades[i].id, categoria=cat, titulo=titulo,
                              descripcion=desc, precio=precio, precio_negociable=neg, telefono=dueno.telefono,
                              whatsapp=True, creado=datetime.now() - timedelta(days=rnd.randint(0, 12)),
                              vence=hoy + timedelta(days=models.DIAS_VIGENCIA_ANUNCIO[cat] - rnd.randint(0, 12))))

    ruta = "documentos/manual_convivencia_demo.pdf"
    (UPLOAD_DIR / "documentos").mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / ruta).write_bytes(pdf_manual())
    db.add(models.Documento(titulo="Manual de convivencia", categoria="manual_convivencia",
                            descripcion="Versión vigente aprobada por la asamblea", nombre_original="Manual de convivencia.pdf",
                            ruta=ruta, publicado_por=admin.id, publicado=datetime.now() - timedelta(days=60)))
