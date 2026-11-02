"""Licencias de prueba del portal de demostración."""
import os
import tempfile
from datetime import date, timedelta

import pytest

if "DATABASE_URL" not in os.environ:
    _tmp = tempfile.mkdtemp()
    os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
    os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"

from fastapi.testclient import TestClient  # noqa: E402

import seed  # noqa: E402
from app import licencias  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import admin as r_admin  # noqa: E402
from app.routers import auth as r_auth  # noqa: E402


@pytest.fixture()
def c(monkeypatch):
    seed.main()
    monkeypatch.setattr(r_auth, "MODO_DEMO", True)
    monkeypatch.setattr(r_auth, "CLAVE_MAESTRA", "maestra-123")
    monkeypatch.setattr(r_admin, "MODO_DEMO", True)
    return TestClient(app)


def test_generar_e_ingresar_como_admin_y_propietario(c):
    r = c.post("/api/auth/licencia/generar", json={"clave_maestra": "maestra-123", "conjunto": "Conjunto Azalea", "dias": 15})
    assert r.status_code == 200, r.text
    lic = r.json()
    assert lic["vence"] == (date.today() + timedelta(days=15)).isoformat()
    assert "?licencia=" in lic["enlace"]

    r = c.post("/api/auth/licencia", json={"codigo": lic["codigo"], "perfil": "administrador"})
    assert r.status_code == 200, r.text
    h = {"Authorization": "Bearer " + r.json()["access_token"]}
    assert r.json()["usuario"]["rol"] == "administrador"
    assert r.json()["licencia"]["conjunto"] == "Conjunto Azalea"
    assert c.get("/api/admin/usuarios", headers=h).status_code == 200

    r = c.post("/api/auth/licencia", json={"codigo": lic["codigo"], "perfil": "propietario"})
    assert r.status_code == 200
    assert r.json()["usuario"]["rol"] == "propietario"


def test_clave_maestra_incorrecta(c):
    r = c.post("/api/auth/licencia/generar", json={"clave_maestra": "otra", "conjunto": "X", "dias": 5})
    assert r.status_code == 401


def test_licencia_alterada_o_vencida(c):
    cod = licencias.generar("Conjunto Azalea", 10)["codigo"]
    cuerpo, firma = cod.split(".")
    otro = licencias.generar("Conjunto Azalea", 90)["codigo"].split(".")[0]
    assert c.post("/api/auth/licencia", json={"codigo": f"{otro}.{firma}"}).status_code == 401
    vencida = licencias.generar("Conjunto Azalea", -1)["codigo"]
    r = c.post("/api/auth/licencia", json={"codigo": vencida})
    assert r.status_code == 401 and "venció" in r.json()["detail"]


def test_demo_no_permite_login_con_clave_ni_tocar_usuarios_demo(c):
    r = c.post("/api/auth/login", json={"email": "admin@conjunto.co", "password": seed.CLAVE_DEMO})
    assert r.status_code == 403
    tok = c.post("/api/auth/licencia", json={"codigo": licencias.generar("Z", 3)["codigo"]}).json()["access_token"]
    h = {"Authorization": "Bearer " + tok}
    usuarios = c.get("/api/admin/usuarios", headers=h).json()
    prop = next(u for u in usuarios if u["email"] == "propietario@conjunto.co")
    assert c.post(f"/api/admin/usuarios/{prop['id']}/restablecer-clave", headers=h).status_code == 400


def test_portal_real_no_acepta_licencias():
    cod = licencias.generar("Z", 3)["codigo"]
    assert TestClient(app).post("/api/auth/licencia", json={"codigo": cod}).status_code == 404
