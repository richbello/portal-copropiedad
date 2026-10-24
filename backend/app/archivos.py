"""Guardado seguro de archivos subidos."""
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from .config import EXTENSIONES_PERMITIDAS, MAX_UPLOAD_MB, UPLOAD_DIR


async def guardar_archivo(archivo: UploadFile, subcarpeta: str) -> tuple[str, str]:
    """Devuelve (nombre_original, ruta_relativa). Nunca usa el nombre del usuario en disco."""
    nombre = Path(archivo.filename or "archivo").name
    ext = Path(nombre).suffix.lower()
    if ext not in EXTENSIONES_PERMITIDAS:
        raise HTTPException(400, f"Tipo de archivo no permitido ({ext}). Permitidos: "
                                 + ", ".join(sorted(EXTENSIONES_PERMITIDAS)))
    contenido = await archivo.read()
    if len(contenido) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(400, f"El archivo supera {MAX_UPLOAD_MB} MB")
    carpeta = UPLOAD_DIR / subcarpeta
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta_rel = f"{subcarpeta}/{uuid.uuid4().hex}{ext}"
    (UPLOAD_DIR / ruta_rel).write_bytes(contenido)
    return nombre, ruta_rel


def ruta_absoluta(ruta_rel: str) -> Path:
    p = (UPLOAD_DIR / ruta_rel).resolve()
    if UPLOAD_DIR.resolve() not in p.parents:
        raise HTTPException(400, "Ruta inválida")
    if not p.exists():
        raise HTTPException(404, "Archivo no encontrado")
    return p
