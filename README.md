# Portal de Propietarios — Propiedad Horizontal

Aplicación web para que los propietarios de un conjunto residencial ingresen con usuario y contraseña, consulten su estado de cuenta, descarguen su paz y salvo, radiquen solicitudes a la administración y vean en qué se gasta el presupuesto. Incluye el panel de la administración para facturar, registrar pagos, gestionar la cartera y responder solicitudes.

**Stack:** FastAPI + SQLAlchemy (Python) · React + Vite · SQLite para desarrollo, PostgreSQL para producción · PDFs con ReportLab · JWT + bcrypt.

---

## Arrancar desde PowerShell (Windows)

```powershell
Set-ExecutionPolicy -Scope Process Bypass   # una vez por ventana
.\portal.ps1 instalar
.\portal.ps1 demo
.\portal.ps1 iniciar        # http://localhost:8000
.\portal.ps1 ayuda          # todos los comandos
```
En Linux, Mac o Codespaces use `./portal.sh` con los mismos comandos.

## Arrancar manualmente

Requisitos: Python 3.11+ y Node 18+.

```bash
# 1. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (en Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
python seed.py                  # crea la base de datos con datos de demostración
uvicorn app.main:app --reload --port 8000

# 2. Frontend (en otra terminal)
cd frontend
npm install
npm run dev                     # abre http://localhost:5173
```

### Usuarios de demostración (clave `Demo2026*`)

| Correo | Rol | Qué ve |
|---|---|---|
| propietario@conjunto.co | Propietario (Torre 1 - 101) | Su saldo, solicitudes, documentos, presupuesto |
| residente@conjunto.co | Residente/arrendatario de la misma unidad | Lo mismo que el propietario |
| admin@conjunto.co | Administración | Todo, incluida la creación de usuarios y parámetros |
| contador@conjunto.co | Contador | Facturación, pagos, importación y cartera |
| consejo@conjunto.co | Consejo de administración | Tablero y cartera en solo lectura |
| revisor@conjunto.co | Revisor fiscal | Solo lectura + registro de auditoría |

La documentación interactiva de la API queda en http://localhost:8000/docs

---

## Qué hace

**Para el propietario**
- Saldo actual con la antigüedad de la deuda (por vencer, 1–30, 31–60, 61–90, más de 90 días).
- Estado de cuenta con todos los cargos y pagos, y saldo acumulado. Descarga en PDF con código de verificación.
- Paz y salvo en PDF, que solo se habilita cuando el saldo es cero.
- Solicitudes con número de radicado, fecha límite en **días hábiles colombianos** (calcula los festivos de la Ley Emiliani para cualquier año), semáforo de vencimiento, conversación con la administración, adjuntos y constancia de radicación en PDF.
- Tipos: daño locativo, reserva de zona común (con validación de cruces de fecha), certificado, queja, derecho de petición (15 días hábiles, Ley 1755/2015), solicitud de documentos, consulta.
- Repositorio de documentos: actas, presupuesto, estados financieros, reglamento, circulares.
- **Transparencia presupuestal:** presupuesto aprobado por rubro frente a lo pagado, con el gasto que debería llevarse a la fecha y alertas de sobreejecución.
- Notificaciones en el portal (y por correo si se configura SMTP).

**Para la administración**
- Tablero: cartera vencida por edades, recaudo del mes, solicitudes abiertas y vencidas, porcentaje de respuestas a tiempo, mayores deudores.
- Cartera por unidad con filtros y exportación a Excel (CSV).
- Facturación mensual automática: cuota = presupuesto mensual × coeficiente de copropiedad (art. 29 Ley 675). No duplica si se ejecuta dos veces.
- Liquidación de intereses de mora sobre el capital vencido, con **bloqueo si la tasa supera el tope legal** configurado (art. 30 Ley 675: 1,5 veces el interés bancario corriente).
- Registro de pagos (con control de referencias duplicadas), cargos individuales y multas.
- Importación de cargos o pagos desde Excel/CSV con **vista previa y validación fila por fila** antes de guardar. Acepta valores con formato colombiano (`$285.000`).
- Gestión de usuarios: creación con clave temporal, asignación de varias unidades, propietario o residente, restablecer clave, desactivar.
- Parámetros (presupuesto mensual, día de vencimiento, tasa de mora, tope legal, cuenta de recaudo).
- Registro de auditoría de todas las acciones: quién, qué, cuándo y desde qué IP.

## Seguridad y cumplimiento

- Contraseñas con bcrypt; política mínima de 8 caracteres con letras y números.
- Bloqueo de 15 minutos tras 5 intentos fallidos.
- Primer ingreso obligatorio: cambio de la clave temporal y **autorización de tratamiento de datos (Ley 1581 de 2012)**, que queda registrada con fecha en la auditoría.
- Un propietario nunca puede ver unidades, cuentas ni solicitudes de otro (verificado en la API, no solo en la pantalla).
- Archivos subidos: lista blanca de extensiones, límite de 10 MB, nombre aleatorio en disco.
- Cabeceras de seguridad HTTP y control de CORS.
- Los pagos y aplicaciones siguen el orden del art. 1653 del Código Civil: primero intereses y luego capital, del más antiguo al más reciente.

## Pruebas

```bash
cd backend
pytest -q
```
15 pruebas de extremo a extremo: festivos colombianos, bloqueo de cuenta, aislamiento entre propietarios, cuadre del estado de cuenta, paz y salvo, flujo completo de solicitud, reservas cruzadas, archivos peligrosos, facturación sin duplicados, tope de intereses, importación con errores, primer ingreso, permisos del consejo y auditoría.

## Paso a producción

1. **Variables de entorno** (copie `backend/.env.example`):
   - `SECRET_KEY`: una clave larga y aleatoria (`python -c "import secrets; print(secrets.token_urlsafe(48))"`).
   - `DATABASE_URL`: `postgresql+psycopg://usuario:clave@host:5432/copropiedad`
   - `NOMBRE_CONJUNTO`, `NIT_CONJUNTO`: aparecen en los PDFs.
   - `SMTP_*`: para enviar correos (Gmail Workspace, SendGrid, Resend, etc.).
   - `CORS_ORIGINS`: el dominio del portal.
2. **Compilar el frontend:** `cd frontend && npm run build`. El backend sirve automáticamente la carpeta `frontend/dist`, así que basta un solo servidor.
3. **Con Docker:** `docker compose up -d --build` levanta PostgreSQL y la aplicación en el puerto 8000.
4. **HTTPS obligatorio** (Render, Railway y la mayoría de VPS con Caddy o Nginx lo dan gratis con Let's Encrypt).
5. **Copias de seguridad diarias** de la base de datos y de la carpeta `uploads`.
6. No ejecute `seed.py` en producción: borra la base de datos. Cree el primer administrador con `python crear_admin.py`.

## Cargar un conjunto real

1. Cree el administrador con `crear_admin.py`.
2. En la API (`/docs`) o con un script, cree las unidades con su torre, número y coeficiente (deben sumar 100%).
3. Cree los propietarios desde **Propietarios y usuarios**; el sistema genera la clave temporal para entregar.
4. Configure los parámetros y el presupuesto aprobado (rubros) de la vigencia.
5. Importe el saldo inicial de cada unidad como un cargo tipo `otro` ("Saldo inicial a corte X") con la plantilla de Excel.
6. Desde ahí: facturar cada mes, importar el extracto de pagos y liquidar intereses.

## Siguientes pasos sugeridos

- Pagos en línea con Wompi o ePayco (PSE), conciliando automáticamente con la referencia.
- Envío de notificaciones por WhatsApp.
- Votaciones y asambleas virtuales con quórum por coeficiente.
- App instalable en el celular (PWA).
- Recuperación de contraseña por correo con enlace de un solo uso.

## Estructura

```
backend/
  app/
    main.py            arranque, rutas y servicio del frontend compilado
    models.py          tablas: usuarios, unidades, cargos, pagos, solicitudes, documentos, presupuesto, auditoría
    security.py        contraseñas, JWT, permisos por rol y por unidad
    cartera.py         estado de cuenta, edades de mora, liquidación de intereses
    fechas.py          días hábiles y festivos de Colombia
    pdfs.py            estado de cuenta, paz y salvo, constancia de radicado
    routers/           auth, cuentas, solicitudes, documentos y presupuesto, admin
  seed.py              datos de demostración
  crear_admin.py       primer administrador en producción
  tests/               pruebas automáticas
frontend/
  src/App.jsx          sesión, menú y rutas por rol
  src/pages/           una pantalla por archivo
```
