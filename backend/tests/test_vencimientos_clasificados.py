"""SOAT y tecnomecánica con avisos, y negocios y clasificados."""
import os
import tempfile
from datetime import date, timedelta

import pytest

_tmp = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ.setdefault("UPLOAD_DIR", f"{_tmp}/uploads")

from fastapi.testclient import TestClient  # noqa: E402

import seed  # noqa: E402
from app import models, vencimientos  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20


@pytest.fixture(scope="module")
def c():
    seed.main()
    return TestClient(app)


def h(c, email):
    r = c.post("/api/auth/login", json={"email": email, "password": seed.CLAVE_DEMO})
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_estados_de_vencimiento():
    hoy = date(2026, 10, 23)
    assert vencimientos.estado(date(2026, 10, 1), hoy)["estado"] == "vencido"
    assert vencimientos.estado(date(2026, 11, 10), hoy) == {"estado": "por_vencer", "dias": 18}
    assert vencimientos.estado(date(2027, 3, 1), hoy)["estado"] == "vigente"
    assert vencimientos.estado(None)["estado"] == "sin_dato"


def test_soat_y_tecnomecanica_por_vehiculo(c):
    p = h(c, "propietario@conjunto.co")
    uid = c.get("/api/auth/me", headers=p).json()["unidades"][0]["id"]
    r = c.post(f"/api/censo/unidades/{uid}/vehiculos", headers=p, json={
        "tipo": "moto", "placa": "abc 12d", "soat_vence": str(date.today() - timedelta(days=3)),
        "tecnomecanica_vence": str(date.today() + timedelta(days=6))})
    assert r.status_code == 200
    moto = next(v for v in c.get(f"/api/censo/unidades/{uid}", headers=p).json()["vehiculos"] if v["placa"] == "ABC12D")
    assert moto["soat"]["estado"] == "vencido" and moto["tecnomecanica"]["estado"] == "por_vencer"
    pendientes = {(d["que"], d["documento"]) for d in c.get("/api/vencimientos/mios", headers=p).json()}
    assert ("moto ABC12D", "soat") in pendientes and ("moto ABC12D", "tecnomecanica") in pendientes
    # Las bicicletas no llevan SOAT
    r = c.post(f"/api/censo/unidades/{uid}/vehiculos", headers=p,
               json={"tipo": "bicicleta", "soat_vence": str(date.today())})
    bici = next(v for v in c.get(f"/api/censo/unidades/{uid}", headers=p).json()["vehiculos"] if v["id"] == r.json()["id"])
    assert "soat" not in bici


def test_avisos_no_se_repiten_y_llegan_a_la_unidad(c):
    p = h(c, "propietario@conjunto.co")
    with SessionLocal() as db:
        primera = vencimientos.revisar(db)
        segunda = vencimientos.revisar(db)
    assert primera > 0 and segunda == 0
    titulos = [n["titulo"] for n in c.get("/api/auth/notificaciones", headers=p).json()]
    assert any("SOAT" in t for t in titulos)
    # Otra unidad no recibe los avisos de esta moto
    otra = h(c, "diana.torres@correo.co")
    assert not any("ABC12D" in n["titulo"] for n in c.get("/api/auth/notificaciones", headers=otra).json())


def test_publicar_y_ver_clasificado(c):
    p, otro = h(c, "propietario@conjunto.co"), h(c, "diana.torres@correo.co")
    r = c.post("/api/clasificados", headers=p,
               data={"categoria": "venta", "titulo": "Vendo comedor de 4 puestos",
                     "descripcion": "Comedor en madera con cuatro sillas, muy buen estado.", "precio": "$450.000"},
               files=[("fotos", ("comedor.png", PNG, "image/png"))])
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["precio"] == 450000 and len(a["fotos"]) == 1 and a["torre"] == "1"
    assert "Ramírez" not in a["publicado_por"]  # solo inicial del apellido
    visto = next(x for x in c.get("/api/clasificados", headers=otro).json() if x["id"] == a["id"])
    assert visto["es_mio"] is False and "reportes" not in visto
    foto = c.get(f"/api/clasificados/{a['id']}/fotos/{a['fotos'][0]}", headers=otro)
    assert foto.status_code == 200 and foto.content == PNG
    # Otro vecino no lo puede editar ni cerrar
    assert c.post(f"/api/clasificados/{a['id']}/cerrar", headers=otro).status_code == 403
    assert c.post(f"/api/clasificados/{a['id']}/cerrar", headers=p).status_code == 200
    assert a["id"] not in [x["id"] for x in c.get("/api/clasificados", headers=otro).json()]


def test_fotos_y_limites(c):
    p = h(c, "propietario@conjunto.co")
    base = {"categoria": "servicio", "titulo": "Paseo de perros", "descripcion": "Paseo perros del conjunto en la tarde."}
    r = c.post("/api/clasificados", headers=p, data=base, files=[("fotos", ("x.pdf", b"%PDF", "application/pdf"))])
    assert r.status_code == 400
    r = c.post("/api/clasificados", headers=p, data=base,
               files=[("fotos", (f"{i}.png", PNG, "image/png")) for i in range(4)])
    assert r.status_code == 400
    assert c.post("/api/clasificados", headers=p, data=dict(base, titulo="Hola")).status_code == 400


def test_vencidos_no_se_muestran_y_se_renuevan(c):
    p = h(c, "propietario@conjunto.co")
    r = c.post("/api/clasificados", headers=p, data={"categoria": "compra", "titulo": "Busco silla de comedor",
                                                       "descripcion": "Busco una silla de comedor en madera clara."})
    aid = r.json()["id"]
    with SessionLocal() as db:
        db.get(models.Anuncio, aid).vence = date.today() - timedelta(days=1)
        db.commit()
    assert aid not in [x["id"] for x in c.get("/api/clasificados", headers=p).json()]
    assert c.post(f"/api/clasificados/{aid}/renovar", headers=p).json()["vigente"] is True
    assert aid in [x["id"] for x in c.get("/api/clasificados", headers=p).json()]


def test_reportar_y_retirar(c):
    p, otro, a = h(c, "propietario@conjunto.co"), h(c, "diana.torres@correo.co"), h(c, "admin@conjunto.co")
    aid = c.post("/api/clasificados", headers=otro, data={
        "categoria": "negocio", "titulo": "Venta de licor a domicilio",
        "descripcion": "Licores a cualquier hora, entrego en portería."}).json()["id"]
    assert c.post(f"/api/clasificados/{aid}/reportar", headers=otro, json={"motivo": "es mío"}).status_code == 400
    assert c.post(f"/api/clasificados/{aid}/reportar", headers=p, json={"motivo": "Prohibido por el manual"}).status_code == 200
    assert c.post(f"/api/clasificados/{aid}/reportar", headers=p, json={"motivo": "Prohibido por el manual"}).status_code == 409
    assert any(x["id"] == aid for x in c.get("/api/clasificados/reportados", headers=a).json())
    assert c.get("/api/clasificados/reportados", headers=p).status_code == 403
    assert c.post(f"/api/clasificados/{aid}/retirar", headers=p, json={"motivo": "No me gusta"}).status_code == 403
    assert c.post(f"/api/clasificados/{aid}/retirar", headers=a, json={"motivo": "Contraría el manual de convivencia"}).status_code == 200
    assert aid not in [x["id"] for x in c.get("/api/clasificados", headers=p).json()]
    mio = next(x for x in c.get("/api/clasificados/mios", headers=otro).json() if x["id"] == aid)
    assert mio["estado"] == "retirado" and "manual" in mio["motivo_retiro"]
    assert any("retirado" in n["titulo"] for n in c.get("/api/auth/notificaciones", headers=otro).json())
