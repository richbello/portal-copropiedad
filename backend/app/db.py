from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def actualizar_esquema() -> list[str]:
    """Crea tablas nuevas y agrega columnas nuevas a tablas existentes.

    Así una base que ya tiene datos se actualiza sola al instalar una versión nueva del portal,
    sin borrar nada. Solo agrega columnas (que siempre son opcionales); nunca elimina ni modifica.
    """
    from . import models  # noqa: F401  (registra todas las tablas en Base.metadata)
    Base.metadata.create_all(engine)
    insp = inspect(engine)
    agregadas = []
    with engine.begin() as con:
        for tabla in Base.metadata.sorted_tables:
            existentes = {c["name"] for c in insp.get_columns(tabla.name)}
            for col in tabla.columns:
                if col.name not in existentes:
                    tipo = col.type.compile(dialect=engine.dialect)
                    con.execute(text(f'ALTER TABLE {tabla.name} ADD COLUMN {col.name} {tipo}'))
                    agregadas.append(f"{tabla.name}.{col.name}")
    return agregadas
