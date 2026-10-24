"""Pruebas de la carga del conjunto real (conjunto.py)."""
import os
import tempfile
from pathlib import Path

import pytest

_tmp = Path(tempfile.mkdtemp())
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/test.db")

import conjunto  # noqa: E402
from app import models  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.security import verificar_password  # noqa: E402


@pytest.fixture()
def datos(tmp_path, monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(conjunto, "DATOS", tmp_path)
    monkeypatch.setattr(conjunto, "UNIDADES_CSV", tmp_path / "unidades.csv")
    monkeypatch.setattr(conjunto, "PROPIETARIOS_CSV", tmp_path / "propietarios.csv")
    monkeypatch.setattr(conjunto, "CLAVES_CSV", tmp_path / "claves_temporales.csv")
    return tmp_path


def test_avellana_216_unidades_suman_100(datos):
    conjunto.main(["generar", "--torres", "9", "--pisos", "6", "--por-piso", "4"])
    conjunto.main(["cargar-unidades", "--confirmar"])
    db = SessionLocal()
    unidades = db.query(models.Unidad).all()
    assert len(unidades) == 216
    assert sum(u.coeficiente for u in unidades) == 100
    assert {(u.torre, u.numero) for u in unidades} >= {("1", "101"), ("5", "501"), ("9", "604")}


def test_coeficientes_que_no_suman_100_se_rechazan(datos):
    conjunto.main(["generar", "--torres", "1", "--pisos", "1", "--por-piso", "2"])
    texto = (datos / "unidades.csv").read_text(encoding="utf-8-sig").replace("50,00000", "40,00000", 1)
    (datos / "unidades.csv").write_text(texto, encoding="utf-8-sig")
    with pytest.raises(SystemExit):
        conjunto.main(["cargar-unidades", "--confirmar"])
    assert SessionLocal().query(models.Unidad).count() == 0


def test_propietarios_varias_unidades_y_residente(datos):
    conjunto.main(["generar", "--torres", "9", "--pisos", "6", "--por-piso", "4"])
    conjunto.main(["cargar-unidades", "--confirmar"])
    conjunto.main(["plantilla-propietarios"])
    lineas = (datos / "propietarios.csv").read_text(encoding="utf-8-sig").splitlines()
    filas = {l.split(";")[0] + "-" + l.split(";")[1]: i for i, l in enumerate(lineas)}
    lineas[filas["5-501"]] = "5;501;Propietario Uno;uno@correo.co;;;propietario"
    lineas[filas["9-604"]] = "9;604;Propietario Uno;uno@correo.co;;;propietario"
    lineas.append("5;501;Arrendatario;arr@correo.co;;;residente")
    (datos / "propietarios.csv").write_text("\n".join(lineas), encoding="utf-8-sig")

    conjunto.main(["cargar-propietarios", "--confirmar"])
    db = SessionLocal()
    uno = db.query(models.Usuario).filter_by(email="uno@correo.co").one()
    assert sorted(uu.unidad.etiqueta for uu in uno.unidades) == ["Torre 5 - 501", "Torre 9 - 604"]
    assert db.query(models.Usuario).filter_by(email="arr@correo.co").one().rol == "residente"

    claves = next(datos.glob("claves_temporales_*.csv")).read_text(encoding="utf-8-sig").splitlines()[1:]
    assert len(claves) == 2
    email, clave = claves[0].split(";")[1], claves[0].split(";")[3]
    assert verificar_password(clave, db.query(models.Usuario).filter_by(email=email).one().password_hash)

    # Cargar de nuevo no duplica usuarios ni asignaciones
    conjunto.main(["cargar-propietarios", "--confirmar"])
    assert SessionLocal().query(models.Usuario).count() == 2
    assert SessionLocal().query(models.UsuarioUnidad).count() == 3
