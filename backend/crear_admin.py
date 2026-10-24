"""Crea el primer usuario administrador en producción (no borra datos).

Uso: python crear_admin.py correo@dominio.co "Nombre Completo"
"""
import secrets
import sys

from sqlalchemy import select

from app import models
from app.db import Base, SessionLocal, engine
from app.security import hash_password


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    email, nombre = sys.argv[1].lower(), sys.argv[2]
    Base.metadata.create_all(engine)
    db = SessionLocal()
    if db.scalar(select(models.Usuario).where(models.Usuario.email == email)):
        print("Ya existe un usuario con ese correo.")
        sys.exit(1)
    clave = secrets.token_urlsafe(9) + "1a"
    db.add(models.Usuario(email=email, nombre=nombre, rol="administrador",
                          password_hash=hash_password(clave), debe_cambiar_password=True))
    for clave_p, valor, desc in [
        ("presupuesto_mensual", "0", "Total mensual de cuotas a distribuir por coeficiente (presupuesto anual / 12)"),
        ("dia_vencimiento", "10", "Día del mes en que vence la cuota de administración"),
        ("tasa_mora_mensual", "0", "Tasa de interés de mora mensual aplicada (%)"),
        ("tope_mora_mensual", "0", "Tope legal mensual (%): 1,5 × interés bancario corriente certificado por la Superfinanciera. Actualizar cada mes."),
        ("cuenta_recaudo", "", "Cuenta para consignaciones"),
    ]:
        if not db.get(models.Parametro, clave_p):
            db.add(models.Parametro(clave=clave_p, valor=valor, descripcion=desc))
    db.commit()
    print(f"Administrador creado: {email}")
    print(f"Clave temporal (cámbiela en el primer ingreso): {clave}")


if __name__ == "__main__":
    main()
