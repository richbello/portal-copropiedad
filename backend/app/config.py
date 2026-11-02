"""Configuración central. Todo se puede sobreescribir con variables de entorno."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Carga backend/.env si existe (sin dependencias externas). Las variables ya definidas tienen prioridad.
_env = BASE_DIR / ".env"
if _env.exists():
    for _linea in _env.read_text(encoding="utf-8").splitlines():
        _linea = _linea.strip()
        if _linea and not _linea.startswith("#") and "=" in _linea:
            _k, _v = _linea.split("=", 1)
            if _v.strip():
                os.environ.setdefault(_k.strip(), _v.strip())

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'copropiedad.db'}")
# Render y otros proveedores entregan "postgres://..." o "postgresql://..."; SQLAlchemy necesita el driver psycopg
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]
SECRET_KEY = os.getenv("SECRET_KEY", "CAMBIAR-ESTA-CLAVE-EN-PRODUCCION")
JWT_ALGORITHM = "HS256"
TOKEN_MINUTOS = int(os.getenv("TOKEN_MINUTOS", "480"))

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_MB = 10
EXTENSIONES_PERMITIDAS = {".pdf", ".jpg", ".jpeg", ".png", ".xlsx", ".docx"}

# Bloqueo por intentos fallidos de login
MAX_INTENTOS_LOGIN = 5
MINUTOS_BLOQUEO = 15

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

# Servidor de demostración: datos ficticios y acceso solo con licencia de prueba
MODO_DEMO = os.getenv("MODO_DEMO", "").lower() in ("1", "true", "si", "sí")
CLAVE_MAESTRA = os.getenv("CLAVE_MAESTRA", "")  # para generar licencias desde /licencias
# Licencias de prueba también en un portal real (p. ej. Avellana mientras no tenga datos reales).
# Ahí la licencia es de SOLO CONSULTA: no puede crear, cambiar ni borrar nada.
PERMITIR_LICENCIAS = MODO_DEMO or os.getenv("PERMITIR_LICENCIAS", "").lower() in ("1", "true", "si", "sí")
LICENCIA_SOLO_CONSULTA = PERMITIR_LICENCIAS and not MODO_DEMO
URL_VERDE360 = os.getenv("URL_VERDE360", "https://richbello.github.io/Ciudad_verde_360/")
DIAS_LICENCIA = int(os.getenv("DIAS_LICENCIA", "15"))
WHATSAPP_VENTAS = os.getenv("WHATSAPP_VENTAS", "573208303847")

# Datos de la copropiedad (aparecen en PDFs)
NOMBRE_CONJUNTO = os.getenv("NOMBRE_CONJUNTO", "Conjunto Avellana Ciudad Verde")
NIT_CONJUNTO = os.getenv("NIT_CONJUNTO", "900.000.000-0")

# Días hábiles de respuesta por tipo de solicitud (Ley 1755 de 2015 para peticiones)
DIAS_RESPUESTA = {
    "derecho_peticion": 15,
    "solicitud_documentos": 10,
    "consulta": 30,
    "dano_locativo": 5,
    "reserva_zona_comun": 3,
    "certificado": 5,
    "queja": 15,
    "otro": 15,
}
