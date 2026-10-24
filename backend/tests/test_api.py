"""Pruebas de extremo a extremo de la API. Ejecutar: pytest -q"""
import os
import tempfile
from datetime import date, timedelta
from io import BytesIO

import pandas as pd
import pytest

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"

from fastapi.testclient import TestClient  # noqa: E402

import seed  # noqa: E402
from app.fechas import festivos, sumar_dias_habiles  # noqa: E402
from app.main import app  # noqa: E402

CLAVE = seed.CLAVE_DEMO


@pytest.fixture(scope="module")
def c():
    seed.main()
    return TestClient(app)


def login(c, email, clave=CLAVE):
    r = c.post("/api/auth/login", json={"email": email, "password": clave})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}, r.json()["usuario"]


def test_festivos_colombia_2026():
    f = festivos(2026)
    for d in ["2026-01-12", "2026-03-23", "2026-04-02", "2026-04-03", "2026-05-18", "2026-06-08",
              "2026-06-15", "2026-06-29", "2026-08-17", "2026-10-12", "2026-11-02", "2026-11-16"]:
        assert date.fromisoformat(d) in f
    # viernes 9 oct 2026 + 2 días hábiles salta el lunes festivo 12 de octubre
    assert sumar_dias_habiles(date(2026, 10, 9), 2) == date(2026, 10, 14)


def test_login_incorrecto_y_bloqueo(c):
    for _ in range(5):
        r = c.post("/api/auth/login", json={"email": "revisor@conjunto.co", "password": "mala"})
        assert r.status_code == 401
    r = c.post("/api/auth/login", json={"email": "revisor@conjunto.co", "password": CLAVE})
    assert r.status_code == 429


def test_sin_token(c):
    assert c.get("/api/auth/me").status_code == 401


def test_propietario_solo_ve_su_unidad(c):
    h, u = login(c, "propietario@conjunto.co")
    propia = u["unidades"][0]["id"]
    assert c.get(f"/api/unidades/{propia}/estado-cuenta", headers=h).status_code == 200
    assert c.get(f"/api/unidades/{propia + 1}/estado-cuenta", headers=h).status_code == 403
    assert c.get("/api/admin/dashboard", headers=h).status_code == 403
    assert c.get("/api/admin/usuarios", headers=h).status_code == 403


def test_estado_cuenta_cuadra(c):
    h, u = login(c, "propietario@conjunto.co")
    ec = c.get(f"/api/unidades/{u['unidades'][0]['id']}/estado-cuenta", headers=h).json()
    assert round(ec["total_cargos"] - ec["total_pagos"], 2) == round(ec["saldo"], 2)
    assert round(sum(ec["edades"].values()), 2) == round(ec["saldo"], 2)
    assert ec["movimientos"][-1]["saldo"] == ec["saldo"]


def test_paz_y_salvo_bloqueado_con_deuda_y_luego_expedido(c):
    h, u = login(c, "propietario@conjunto.co")
    uid = u["unidades"][0]["id"]
    assert c.get(f"/api/unidades/{uid}/paz-y-salvo.pdf", headers=h).status_code == 400
    ha, _ = login(c, "admin@conjunto.co")
    saldo = c.get(f"/api/unidades/{uid}/estado-cuenta", headers=h).json()["saldo"]
    r = c.post("/api/admin/pagos", headers=ha, json={"unidad_id": uid, "fecha": str(date.today()),
                                                     "valor": saldo, "referencia": "TEST-PYS"})
    assert r.status_code == 200
    r = c.get(f"/api/unidades/{uid}/paz-y-salvo.pdf", headers=h)
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    # pago duplicado con la misma referencia
    r = c.post("/api/admin/pagos", headers=ha, json={"unidad_id": uid, "fecha": str(date.today()),
                                                     "valor": 1000, "referencia": "TEST-PYS"})
    assert r.status_code == 409


def test_flujo_solicitud_completo(c):
    h, u = login(c, "propietario@conjunto.co")
    r = c.post("/api/solicitudes", headers=h,
               data={"tipo": "dano_locativo", "asunto": "Puerta de parqueadero dañada",
                     "descripcion": "La puerta vehicular no cierra completamente desde ayer."},
               files=[("archivos", ("foto.png", b"\x89PNG fake", "image/png"))])
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["estado"] == "radicada" and s["radicado"].startswith("SOL-") and len(s["adjuntos"]) == 1

    # el propietario no puede cambiar el estado
    r = c.post(f"/api/solicitudes/{s['id']}/mensajes", headers=h, data={"texto": "¿novedades?", "estado": "cerrada"})
    assert r.status_code == 403

    ha, _ = login(c, "admin@conjunto.co")
    r = c.post(f"/api/solicitudes/{s['id']}/mensajes", headers=ha,
               data={"texto": "Técnico asignado para mañana.", "estado": "respondida"})
    assert r.json()["estado"] == "respondida" and r.json()["fecha_cierre"]

    notifs = c.get("/api/auth/notificaciones", headers=h).json()
    assert any(s["radicado"] in n["titulo"] for n in notifs)
    assert c.get(f"/api/solicitudes/{s['id']}/constancia.pdf", headers=h).content[:4] == b"%PDF"

    # otro propietario no la ve
    h2, _ = login(c, "diana.torres@correo.co")
    assert c.get(f"/api/solicitudes/{s['id']}", headers=h2).status_code == 403


def test_reserva_doble_rechazada(c):
    h, _ = login(c, "propietario@conjunto.co")
    f = str(date.today() + timedelta(days=20))
    datos = {"tipo": "reserva_zona_comun", "asunto": "Reserva BBQ", "descripcion": "Asado familiar el domingo",
             "zona_comun": "BBQ", "fecha_reserva": f}
    assert c.post("/api/solicitudes", headers=h, data=datos).status_code == 200
    assert c.post("/api/solicitudes", headers=h, data=datos).status_code == 409


def test_adjunto_peligroso_rechazado(c):
    h, _ = login(c, "propietario@conjunto.co")
    r = c.post("/api/solicitudes", headers=h,
               data={"tipo": "queja", "asunto": "Prueba archivo", "descripcion": "Intento subir un ejecutable"},
               files=[("archivos", ("virus.exe", b"MZ", "application/octet-stream"))])
    assert r.status_code == 400


def test_facturacion_no_duplica(c):
    ha, _ = login(c, "admin@conjunto.co")
    r = c.post("/api/admin/facturar", headers=ha, json={"periodo": "2030-01"})
    assert r.json()["creados"] == 24
    r = c.post("/api/admin/facturar", headers=ha, json={"periodo": "2030-01"})
    assert r.json()["creados"] == 0 and r.json()["omitidos_ya_facturados"] == 24


def test_intereses_respetan_tope(c):
    ha, _ = login(c, "admin@conjunto.co")
    r = c.post("/api/admin/liquidar-intereses", headers=ha,
               json={"periodo": "2029-12", "fecha_corte": str(date.today()), "tasa_mensual_pct": "3.5"})
    assert r.status_code == 400
    r = c.post("/api/admin/liquidar-intereses", headers=ha,
               json={"periodo": "2029-12", "fecha_corte": str(date.today())})
    assert r.status_code == 200 and r.json()["unidades"] > 0
    r2 = c.post("/api/admin/liquidar-intereses", headers=ha,
                json={"periodo": "2029-12", "fecha_corte": str(date.today())})
    assert r2.json()["unidades"] == 0


def test_importar_excel_con_vista_previa(c):
    ha, _ = login(c, "admin@conjunto.co")
    df = pd.DataFrame([["1", "101", "2031-02", "administracion", "Cuota feb", "$285.000", "2031-02-10"],
                       ["9", "999", "2031-02", "administracion", "No existe", "1000", "2031-02-10"]],
                      columns=["torre", "numero", "periodo", "tipo", "concepto", "valor", "fecha_vencimiento"])
    buf = BytesIO()
    df.to_excel(buf, index=False)
    archivo = ("cargos.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r = c.post("/api/admin/importar", headers=ha, data={"tipo": "cargos", "confirmar": "false"},
               files={"archivo": archivo})
    j = r.json()
    assert j["filas_validas"] == 1 and len(j["errores"]) == 1 and j["total"] == 285000
    r = c.post("/api/admin/importar", headers=ha, data={"tipo": "cargos", "confirmar": "true"},
               files={"archivo": archivo})
    assert r.status_code == 400  # no importa si hay errores


def test_crear_usuario_y_primer_ingreso(c):
    ha, _ = login(c, "admin@conjunto.co")
    r = c.post("/api/admin/usuarios", headers=ha,
               json={"email": "nuevo@correo.co", "nombre": "Nuevo Propietario", "unidad_id": 2})
    assert r.status_code == 200
    clave = r.json()["clave_temporal"]
    h, u = login(c, "nuevo@correo.co", clave)
    assert u["debe_cambiar_password"] is True
    assert c.post("/api/auth/cambiar-password", headers=h,
                  json={"actual": clave, "nueva": "corta"}).status_code == 400
    assert c.post("/api/auth/cambiar-password", headers=h,
                  json={"actual": clave, "nueva": "NuevaClave2026"}).status_code == 200
    _, u = login(c, "nuevo@correo.co", "NuevaClave2026")
    assert u["debe_cambiar_password"] is False


def test_consejo_lee_pero_no_modifica(c):
    hc, _ = login(c, "consejo@conjunto.co")
    assert c.get("/api/admin/cartera", headers=hc).status_code == 200
    assert c.post("/api/admin/facturar", headers=hc, json={"periodo": "2032-01"}).status_code == 403


def test_auditoria_registra(c):
    ha, _ = login(c, "admin@conjunto.co")
    acciones = {a["accion"] for a in c.get("/api/admin/auditoria", headers=ha).json()}
    assert {"login", "registrar_pago", "radicar_solicitud", "facturar_periodo"} <= acciones
