"""Carga del conjunto real desde la terminal: unidades, coeficientes y propietarios.

Los archivos se guardan en backend/datos/ (excluida de Git, porque contiene datos personales).
Los CSV usan ';' y codificación UTF-8 con BOM para abrirse bien en Excel en español.

Comandos:
  python conjunto.py generar --torres 9 --pisos 6 --por-piso 4
      Crea datos/unidades.csv con todas las unidades y coeficientes iguales (provisionales).
  python conjunto.py cargar-unidades [--confirmar]
      Valida datos/unidades.csv (coeficientes deben sumar 100%) y lo carga en la base.
  python conjunto.py plantilla-propietarios
      Crea datos/propietarios.csv con una fila por unidad para llenar en Excel.
  python conjunto.py cargar-propietarios [--confirmar]
      Crea los usuarios, los asigna a sus unidades y genera datos/claves_temporales.csv.
  python conjunto.py resumen
      Muestra cuántas unidades y usuarios hay en la base.

Sin --confirmar solo se revisa el archivo y se muestran los errores; no se guarda nada.
"""
import argparse
import csv
import secrets
import string
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import func, select

from app import models
from app.db import Base, SessionLocal, engine
from app.security import hash_password

DATOS = Path(__file__).resolve().parent / "datos"
UNIDADES_CSV = DATOS / "unidades.csv"
PROPIETARIOS_CSV = DATOS / "propietarios.csv"
CLAVES_CSV = DATOS / "claves_temporales.csv"
COLS_UNIDADES = ["torre", "numero", "tipo", "coeficiente", "area_m2"]
COLS_PROPIETARIOS = ["torre", "numero", "nombre", "email", "documento", "telefono", "relacion"]


def _escribir_csv(ruta: Path, columnas: list[str], filas: list[dict]) -> None:
    DATOS.mkdir(exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=columnas, delimiter=";")
        w.writeheader()
        w.writerows(filas)


def _leer_csv(ruta: Path) -> list[dict]:
    if not ruta.exists():
        sys.exit(f"No existe {ruta}. Genérelo primero (vea: python conjunto.py --help).")
    texto = ruta.read_text(encoding="utf-8-sig")
    delim = ";" if texto.splitlines()[0].count(";") >= texto.splitlines()[0].count(",") else ","
    filas = list(csv.DictReader(texto.splitlines(), delimiter=delim))
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in f.items()} for f in filas]


def _decimal(valor: str) -> Decimal:
    """Acepta 0.46296 y 0,46296 (Excel en español)."""
    return Decimal(valor.replace(" ", "").replace(",", "."))


def _coma(valor: Decimal) -> str:
    """Decimal con coma, como lo espera Excel en español (evita que 0.46296 se lea como 46.296)."""
    return str(valor).replace(".", ",")


def _clave_temporal() -> str:
    alfabeto = string.ascii_letters + string.digits
    while True:
        c = "".join(secrets.choice(alfabeto) for _ in range(10))
        if any(ch.isdigit() for ch in c) and any(ch.isalpha() for ch in c):
            return c


def generar(torres: int, pisos: int, por_piso: int, forzar: bool) -> None:
    if UNIDADES_CSV.exists() and not forzar:
        sys.exit(f"{UNIDADES_CSV} ya existe. Use --forzar para reemplazarlo.")
    total = torres * pisos * por_piso
    base = (Decimal(100) / total).quantize(Decimal("0.00001"))
    filas = []
    for t in range(1, torres + 1):
        for p in range(1, pisos + 1):
            for a in range(1, por_piso + 1):
                filas.append({"torre": str(t), "numero": f"{p}{a:02d}", "tipo": "apartamento",
                              "coeficiente": _coma(base), "area_m2": ""})
    # Ajuste del redondeo en la última unidad para que la suma dé exactamente 100
    filas[-1]["coeficiente"] = _coma(Decimal(100) - base * (total - 1))
    _escribir_csv(UNIDADES_CSV, COLS_UNIDADES, filas)
    print(f"{total} unidades generadas en {UNIDADES_CSV}")
    print(f"  {torres} torres × {pisos} pisos × {por_piso} apartamentos por piso")
    print(f"  Numeración: torre 1 apto 101 ... torre {torres} apto {pisos}{por_piso:02d}")
    print(f"  Coeficiente provisional igual para todas: {base}%")
    print("IMPORTANTE: reemplace los coeficientes y áreas por los del reglamento de propiedad")
    print("horizontal antes de facturar. Puede editar el archivo en Excel y luego cargarlo.")


def cargar_unidades(confirmar: bool) -> None:
    filas = _leer_csv(UNIDADES_CSV)
    errores, vistas, suma = [], set(), Decimal(0)
    limpias = []
    for i, f in enumerate(filas, start=2):
        torre, numero = f.get("torre", ""), f.get("numero", "")
        if not torre or not numero:
            errores.append(f"Fila {i}: falta torre o número")
            continue
        if (torre, numero) in vistas:
            errores.append(f"Fila {i}: unidad T{torre}-{numero} repetida")
            continue
        vistas.add((torre, numero))
        try:
            coef = _decimal(f.get("coeficiente", ""))
            if coef <= 0:
                raise InvalidOperation
        except InvalidOperation:
            errores.append(f"Fila {i}: coeficiente inválido '{f.get('coeficiente')}'")
            continue
        area = None
        if f.get("area_m2"):
            try:
                area = _decimal(f["area_m2"])
            except InvalidOperation:
                errores.append(f"Fila {i}: área inválida '{f['area_m2']}'")
                continue
        suma += coef
        limpias.append((torre, numero, f.get("tipo") or "apartamento", coef, area))

    print(f"Filas leídas: {len(filas)}   Unidades válidas: {len(limpias)}")
    print(f"Suma de coeficientes: {suma}%")
    if abs(suma - 100) > Decimal("0.01"):
        errores.append(f"Los coeficientes suman {suma}% y deben sumar 100% (art. 25-27 Ley 675 de 2001)")
    if errores:
        print("\nErrores encontrados (corrija el archivo y vuelva a intentar):")
        for e in errores[:50]:
            print("  -", e)
        if len(errores) > 50:
            print(f"  ... y {len(errores) - 50} más")
        sys.exit(1)
    if not confirmar:
        print("\nEl archivo está correcto. Para guardarlo en la base agregue --confirmar")
        return

    Base.metadata.create_all(engine)
    db = SessionLocal()
    existentes = {(u.torre, u.numero): u for u in db.scalars(select(models.Unidad))}
    creadas = actualizadas = 0
    for torre, numero, tipo, coef, area in limpias:
        u = existentes.get((torre, numero))
        if u:
            u.coeficiente, u.area_m2, u.tipo = coef, area, tipo
            actualizadas += 1
        else:
            db.add(models.Unidad(torre=torre, numero=numero, tipo=tipo, coeficiente=coef, area_m2=area))
            creadas += 1
    db.add(models.Auditoria(accion="cargar_unidades",
                            detalle=f"terminal: creadas={creadas} actualizadas={actualizadas} suma={suma}"))
    db.commit()
    print(f"\nListo: {creadas} unidades creadas, {actualizadas} actualizadas.")


def plantilla_propietarios(forzar: bool) -> None:
    if PROPIETARIOS_CSV.exists() and not forzar:
        sys.exit(f"{PROPIETARIOS_CSV} ya existe. Use --forzar para reemplazarlo.")
    Base.metadata.create_all(engine)
    db = SessionLocal()
    unidades = db.scalars(select(models.Unidad)).all()
    if not unidades:
        sys.exit("No hay unidades en la base. Cargue primero las unidades (cargar-unidades --confirmar).")
    unidades.sort(key=lambda u: (int(u.torre) if u.torre.isdigit() else u.torre,
                                 int(u.numero) if u.numero.isdigit() else u.numero))
    filas = [{"torre": u.torre, "numero": u.numero, "nombre": "", "email": "", "documento": "",
              "telefono": "", "relacion": "propietario"} for u in unidades]
    _escribir_csv(PROPIETARIOS_CSV, COLS_PROPIETARIOS, filas)
    print(f"Plantilla con {len(filas)} unidades en {PROPIETARIOS_CSV}")
    print("Llene nombre y correo de cada propietario. Las filas sin correo se omiten al cargar.")
    print("Para un arrendatario, copie la fila de la unidad y ponga relacion = residente.")
    print("Un mismo correo en varias filas = una persona con varias unidades.")


def cargar_propietarios(confirmar: bool) -> None:
    filas = _leer_csv(PROPIETARIOS_CSV)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    unidades = {(u.torre, u.numero): u for u in db.scalars(select(models.Unidad))}
    usuarios = {u.email.lower(): u for u in db.scalars(select(models.Usuario))}
    errores, validas, omitidas = [], [], 0
    nombres_por_email: dict[str, str] = {}
    for i, f in enumerate(filas, start=2):
        email = f.get("email", "").lower()
        if not email:
            omitidas += 1
            continue
        if "@" not in email or "." not in email.split("@")[-1]:
            errores.append(f"Fila {i}: correo inválido '{email}'")
            continue
        unidad = unidades.get((f.get("torre", ""), f.get("numero", "")))
        if not unidad:
            errores.append(f"Fila {i}: la unidad T{f.get('torre')}-{f.get('numero')} no existe")
            continue
        nombre = f.get("nombre", "")
        if not nombre:
            errores.append(f"Fila {i}: falta el nombre de {email}")
            continue
        if nombres_por_email.setdefault(email, nombre) != nombre:
            errores.append(f"Fila {i}: el correo {email} aparece con dos nombres distintos")
            continue
        relacion = (f.get("relacion") or "propietario").lower()
        if relacion not in ("propietario", "residente"):
            errores.append(f"Fila {i}: relación '{relacion}' debe ser propietario o residente")
            continue
        validas.append((email, nombre, f.get("documento") or None, f.get("telefono") or None, unidad, relacion))

    personas_nuevas = {v[0] for v in validas if v[0] not in usuarios}
    print(f"Filas con correo: {len(validas) + len(errores)}   Sin correo (omitidas): {omitidas}")
    print(f"Personas nuevas: {len(personas_nuevas)}   Ya existentes: {len({v[0] for v in validas}) - len(personas_nuevas)}")
    if errores:
        print("\nErrores encontrados (corrija el archivo y vuelva a intentar):")
        for e in errores[:50]:
            print("  -", e)
        sys.exit(1)
    if not confirmar:
        print("\nEl archivo está correcto. Para crear los usuarios agregue --confirmar")
        return

    claves, asignaciones = [], 0
    for email, nombre, documento, telefono, unidad, relacion in validas:
        u = usuarios.get(email)
        if not u:
            clave = _clave_temporal()
            rol = "residente" if relacion == "residente" else "propietario"
            u = models.Usuario(email=email, nombre=nombre, rol=rol, documento=documento, telefono=telefono,
                               password_hash=hash_password(clave), debe_cambiar_password=True)
            db.add(u)
            db.flush()
            usuarios[email] = u
            claves.append({"nombre": nombre, "email": email, "clave_temporal": clave, "unidades": ""})
        ya = db.scalar(select(models.UsuarioUnidad).where(models.UsuarioUnidad.usuario_id == u.id,
                                                          models.UsuarioUnidad.unidad_id == unidad.id))
        if not ya:
            db.add(models.UsuarioUnidad(usuario_id=u.id, unidad_id=unidad.id, relacion=relacion))
            asignaciones += 1
        for c in claves:
            if c["email"] == email:
                c["unidades"] = (c["unidades"] + ", " if c["unidades"] else "") + unidad.etiqueta
    db.add(models.Auditoria(accion="cargar_propietarios",
                            detalle=f"terminal: usuarios_nuevos={len(claves)} asignaciones={asignaciones}"))
    db.commit()
    if claves:
        sello = datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta = CLAVES_CSV.with_name(f"claves_temporales_{sello}.csv")
        _escribir_csv(ruta, ["nombre", "email", "unidades", "clave_temporal"], claves)
        print(f"\nListo: {len(claves)} usuarios creados y {asignaciones} asignaciones de unidad.")
        print(f"Claves temporales en: {ruta}")
        print("Entréguelas de forma privada a cada persona y borre el archivo después.")
        print("En el primer ingreso cada uno debe cambiar la clave y autorizar el tratamiento de datos.")
    else:
        print(f"\nListo: no había personas nuevas. {asignaciones} asignaciones de unidad agregadas.")


def resumen() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    n_unidades = db.scalar(select(func.count()).select_from(models.Unidad))
    suma = db.scalar(select(func.coalesce(func.sum(models.Unidad.coeficiente), 0)))
    torres = db.scalars(select(models.Unidad.torre).distinct()).all()
    print(f"Unidades: {n_unidades} en {len(torres)} torres   Suma de coeficientes: {Decimal(str(suma)):.5f}%")
    for rol in models.ROLES:
        n = db.scalar(select(func.count()).select_from(models.Usuario).where(models.Usuario.rol == rol))
        if n:
            print(f"  {rol}: {n}")
    sin = db.scalar(select(func.count()).select_from(models.Unidad)
                    .where(~models.Unidad.id.in_(select(models.UsuarioUnidad.unidad_id))))
    print(f"Unidades sin ningún usuario asignado: {sin}")


def main(argv=None):
    p = argparse.ArgumentParser(description="Carga del conjunto real", formatter_class=argparse.RawTextHelpFormatter,
                                epilog=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generar", help="Genera datos/unidades.csv")
    g.add_argument("--torres", type=int, required=True)
    g.add_argument("--pisos", type=int, required=True)
    g.add_argument("--por-piso", type=int, required=True)
    g.add_argument("--forzar", action="store_true")
    c = sub.add_parser("cargar-unidades", help="Valida y carga datos/unidades.csv")
    c.add_argument("--confirmar", action="store_true")
    t = sub.add_parser("plantilla-propietarios", help="Genera datos/propietarios.csv")
    t.add_argument("--forzar", action="store_true")
    cp = sub.add_parser("cargar-propietarios", help="Crea usuarios desde datos/propietarios.csv")
    cp.add_argument("--confirmar", action="store_true")
    sub.add_parser("resumen", help="Resumen de lo cargado")
    a = p.parse_args(argv)
    if a.cmd == "generar":
        generar(a.torres, a.pisos, a.por_piso, a.forzar)
    elif a.cmd == "cargar-unidades":
        cargar_unidades(a.confirmar)
    elif a.cmd == "plantilla-propietarios":
        plantilla_propietarios(a.forzar)
    elif a.cmd == "cargar-propietarios":
        cargar_propietarios(a.confirmar)
    else:
        resumen()


if __name__ == "__main__":
    main()
