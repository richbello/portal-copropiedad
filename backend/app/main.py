import logging
import mimetypes
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import (CORS_ORIGINS, DIAS_LICENCIA, LICENCIA_SOLO_CONSULTA, MODO_DEMO, NOMBRE_CONJUNTO,
                     PERMITIR_LICENCIAS, URL_VERDE360, WHATSAPP_VENTAS)
from contextlib import asynccontextmanager

from .db import actualizar_esquema
from .routers import admin, auth, clasificados, comunidad, cuentas, documentos, solicitudes
from .vencimientos import iniciar_revision_periodica

logging.basicConfig(level=logging.INFO)
mimetypes.add_type("application/manifest+json", ".webmanifest")
_nuevas = actualizar_esquema()
if MODO_DEMO:
    # El servidor de demostración arranca siempre con datos ficticios (nunca con datos reales)
    from sqlalchemy import func, select

    from . import models as _m
    from .db import SessionLocal
    with SessionLocal() as _db:
        _vacia = not _db.scalar(select(func.count()).select_from(_m.Usuario))
    if _vacia:
        import seed
        seed.main()
        logging.getLogger("portal").info("Portal de demostración: datos ficticios cargados")
if _nuevas:
    logging.getLogger("portal").info("Base de datos actualizada, columnas nuevas: %s", ", ".join(_nuevas))


@asynccontextmanager
async def ciclo_de_vida(app):
    iniciar_revision_periodica()
    yield


app = FastAPI(title=f"Portal de Propietarios - {NOMBRE_CONJUNTO}", version="1.1.0", lifespan=ciclo_de_vida)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def cabeceras_seguridad(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    return resp


for r in (auth.router, cuentas.router, solicitudes.router, documentos.router, comunidad.router,
          clasificados.router, admin.router):
    app.include_router(r)


@app.get("/api/salud")
def salud():
    datos = {"ok": True, "conjunto": NOMBRE_CONJUNTO}
    if PERMITIR_LICENCIAS:
        datos.update(demo=MODO_DEMO, licencias=True, solo_consulta=LICENCIA_SOLO_CONSULTA,
                     dias_licencia=DIAS_LICENCIA, whatsapp=WHATSAPP_VENTAS, verde360=URL_VERDE360)
    return datos


# En producción el frontend compilado se sirve desde el mismo servidor
DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{ruta:path}", include_in_schema=False)
    def spa(ruta: str):
        archivo = DIST / ruta
        if ruta and archivo.is_file() and DIST in archivo.resolve().parents:
            return FileResponse(archivo)
        return FileResponse(DIST / "index.html")
