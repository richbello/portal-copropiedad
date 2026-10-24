import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import CORS_ORIGINS, NOMBRE_CONJUNTO
from contextlib import asynccontextmanager

from .db import actualizar_esquema
from .routers import admin, auth, clasificados, comunidad, cuentas, documentos, solicitudes
from .vencimientos import iniciar_revision_periodica

logging.basicConfig(level=logging.INFO)
_nuevas = actualizar_esquema()
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
    return {"ok": True, "conjunto": NOMBRE_CONJUNTO}


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
