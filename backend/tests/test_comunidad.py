"""Calendario, censo, parqueaderos y manual de convivencia."""
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest

_tmp = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ.setdefault("UPLOAD_DIR", f"{_tmp}/uploads")

from fastapi.testclient import TestClient  # noqa: E402

import seed  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def c():
    seed.main()
    return TestClient(app)


def h(c, email):
    r = c.post("/api/auth/login", json={"email": email, "password": seed.CLAVE_DEMO})
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def unidad_propia(c, hd):
    return c.get("/api/auth/me", headers=hd).json()["unidades"][0]["id"]


def test_calendario_todos_ven_solo_admin_crea(c):
    p, a = h(c, "propietario@conjunto.co"), h(c, "admin@conjunto.co")
    antes = len(c.get("/api/eventos", headers=p).json())
    evento = {"titulo": "Bazar navideño", "categoria": "cultural", "lugar": "Salón comunal",
              "inicio": (datetime.now() + timedelta(days=20)).isoformat(timespec="minutes"),
              "notificar_todos": True}
    assert c.post("/api/eventos", headers=p, json=evento).status_code == 403
    r = c.post("/api/eventos", headers=a, json=evento)
    assert r.status_code == 200
    assert len(c.get("/api/eventos", headers=p).json()) == antes + 1
    assert any("Bazar navideño" in n["titulo"] for n in c.get("/api/auth/notificaciones", headers=p).json())
    malo = dict(evento, fin=(datetime.now() + timedelta(days=19)).isoformat(timespec="minutes"))
    assert c.post("/api/eventos", headers=a, json=malo).status_code == 400
    assert c.delete(f"/api/eventos/{r.json()['id']}", headers=a).status_code == 200


def test_censo_solo_propia_unidad(c):
    p = h(c, "propietario@conjunto.co")
    uid = unidad_propia(c, p)
    r = c.post(f"/api/censo/unidades/{uid}/mascotas", headers=p,
               json={"nombre": "Kira", "especie": "perro", "raza": "Pitbull", "potencialmente_peligrosa": True})
    assert r.status_code == 200
    censo = c.get(f"/api/censo/unidades/{uid}", headers=p).json()
    kira = [m for m in censo["mascotas"] if m["nombre"] == "Kira"][0]
    assert kira["falta_poliza"] is True
    # otra unidad: ni ver ni escribir
    assert c.get(f"/api/censo/unidades/{uid + 1}", headers=p).status_code == 403
    assert c.post(f"/api/censo/unidades/{uid + 1}/personas", headers=p, json={"nombre": "Intruso X"}).status_code == 403
    # menores: no se guarda documento
    r = c.post(f"/api/censo/unidades/{uid}/personas", headers=p,
               json={"nombre": "Niño Prueba", "menor_de_edad": True, "documento": "123"})
    pid = r.json()["id"]
    persona = [x for x in c.get(f"/api/censo/unidades/{uid}", headers=p).json()["personas"] if x["id"] == pid][0]
    assert persona["documento"] is None
    # vehículo sin placa no se acepta (salvo bicicleta)
    assert c.post(f"/api/censo/unidades/{uid}/vehiculos", headers=p, json={"tipo": "moto"}).status_code == 400
    assert c.post(f"/api/censo/unidades/{uid}/vehiculos", headers=p, json={"tipo": "bicicleta"}).status_code == 200
    assert c.post(f"/api/censo/unidades/{uid}/confirmar", headers=p).status_code == 200
    assert c.get(f"/api/censo/unidades/{uid}", headers=p).json()["vigente"] is True


def test_censo_consejo_ve_totales_no_datos_personales(c):
    k = h(c, "consejo@conjunto.co")
    assert c.get("/api/censo/resumen", headers=k).status_code == 200
    assert c.get("/api/censo/unidades", headers=k).status_code == 403
    assert c.get("/api/censo/exportar.csv", headers=k).status_code == 403
    assert c.get("/api/censo/unidades/1", headers=k).status_code == 403
    a = h(c, "admin@conjunto.co")
    csv = c.get("/api/censo/exportar.csv", headers=a)
    assert csv.status_code == 200 and "mascota" in csv.text


def test_sorteo_parqueaderos_justo(c):
    a = h(c, "admin@conjunto.co")
    previo = c.post("/api/parqueaderos/sorteo", headers=a, json={"tipo": "bicicleta"}).json()
    assert previo["participantes"] > 0 and previo["cupos"] > 0
    r = c.post("/api/parqueaderos/sorteo", headers=a, json={"tipo": "bicicleta", "confirmar": True}).json()
    unidades = [x["unidad"] for x in r["asignados"]]
    codigos = [x["parqueadero"] for x in r["asignados"]]
    assert len(unidades) == len(set(unidades)) == min(previo["participantes"], previo["cupos"])
    assert len(codigos) == len(set(codigos))
    assert r["semilla"] in str(c.get("/api/admin/auditoria", headers=a).json())
    # los ganadores ya no están en espera
    assert not set(unidades) & {e["unidad"] for e in c.get("/api/parqueaderos/espera/bicicleta", headers=a).json()}


def test_asignacion_manual_valida_tipo_y_ocupacion(c):
    a = h(c, "admin@conjunto.co")
    datos = c.get("/api/parqueaderos?tipo=carro", headers=a).json()["parqueaderos"]
    ocupado = next(p for p in datos if p["unidad_id"])
    otra = ocupado["unidad_id"] % 24 + 1
    assert c.put(f"/api/parqueaderos/{ocupado['id']}/asignar", headers=a, json={"unidad_id": otra}).status_code == 409
    visit = next(p for p in datos if p["visitantes"])
    assert c.put(f"/api/parqueaderos/{visit['id']}/asignar", headers=a, json={"unidad_id": otra}).status_code == 400
    assert c.put(f"/api/parqueaderos/{ocupado['id']}/liberar", headers=a).status_code == 200
    p = h(c, "propietario@conjunto.co")
    assert c.put(f"/api/parqueaderos/{ocupado['id']}/asignar", headers=p, json={"unidad_id": 1}).status_code == 403


def test_manual_de_convivencia(c):
    p = h(c, "propietario@conjunto.co")
    m = c.get("/api/manual-convivencia", headers=p).json()
    assert m["vigente"]["titulo"] == "Manual de convivencia"
    r = c.get(f"/api/documentos/{m['vigente']['id']}/ver", headers=p)
    assert r.status_code == 200 and r.content[:4] == b"%PDF" and r.headers["content-disposition"].startswith("inline")
