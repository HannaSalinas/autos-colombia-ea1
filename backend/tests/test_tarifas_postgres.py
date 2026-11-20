"""Iteración 3: consultar y actualizar tarifas (HU-26, HU-27; casos TA-01 a TA-05 del plan PP-03).

La inmutabilidad en la base (TA-06) está en test_migraciones_ea3_postgres.py.
"""

import pytest
from sqlalchemy import func, select

from conftest import autenticar, crear_tarifa, datos_cliente, placa_aleatoria
from app.models import Cliente, Tarifa, Vehiculo
from app.services.autenticacion import SIN_PERMISO


def cantidad(session) -> int:
    return session.scalar(select(func.count()).select_from(Tarifa))


def test_vigentes_de_los_tres_tipos_e_historial_con_autor(api_y_sesion):
    api, session = api_y_sesion
    crear_tarifa(session, "MOTO", 60000)
    crear_tarifa(session, "AUTOMOVIL", 110000)
    crear_tarifa(session, "CAMIONETA", 140000)
    # Cambio de tarifa de AUTOMOVIL hecho por el Administrador de la sesión.
    nueva = api.post("/tarifas", json={"tipo_vehiculo": "AUTOMOVIL", "valor": 120000})
    assert nueva.status_code == 201, nueva.json()
    vigentes = api.get("/tarifas").json()
    assert [(v["tipo_vehiculo"], v["tarifa"]["valor"]) for v in vigentes] == [
        ("MOTO", 60000), ("AUTOMOVIL", 120000), ("CAMIONETA", 140000)]
    historial = api.get("/tarifas/historial?tipo=AUTOMOVIL&limit=100").json()
    assert [t["valor"] for t in historial["items"]][:2] == [120000, 110000]   # la más reciente primero
    assert historial["items"][0]["definida_por"].startswith("Persona ")         # "Nombre (usuario)"
    assert "(prueba." in historial["items"][0]["definida_por"]
    assert historial["items"][1]["definida_por"] is None                          # creada como semilla
    assert all(t["tipo_vehiculo"] == "AUTOMOVIL" for t in historial["items"])


@pytest.mark.parametrize("valor", [1000, 2000000])
def test_actualizar_tarifa_en_los_limites_crea_una_nueva(api_y_sesion, valor):
    api, session = api_y_sesion
    anterior = crear_tarifa(session, "MOTO", 60000)
    antes = cantidad(session)
    respuesta = api.post("/tarifas", json={"tipo_vehiculo": "MOTO", "valor": valor})
    assert respuesta.status_code == 201
    tarifa = respuesta.json()
    assert tarifa["valor"] == valor and tarifa["tipo_vehiculo"] == "MOTO" and tarifa["vigente_desde"]
    assert cantidad(session) == antes + 1
    # La anterior no cambia: se conserva en el historial.
    session.refresh(anterior)
    assert anterior.valor == 60000
    assert next(v for v in api.get("/tarifas").json() if v["tipo_vehiculo"] == "MOTO")["tarifa"]["valor"] == valor


@pytest.mark.parametrize("cuerpo", [
    {"tipo_vehiculo": "MOTO", "valor": 999}, {"tipo_vehiculo": "MOTO", "valor": 2000001},
    {"tipo_vehiculo": "MOTO", "valor": 1000.5}, {"tipo_vehiculo": "MOTO", "valor": 120000.0},
    {"tipo_vehiculo": "MOTO", "valor": ""}, {"tipo_vehiculo": "MOTO", "valor": None},
    {"tipo_vehiculo": "MOTO", "valor": "120000"}, {"tipo_vehiculo": "MOTO"},
    {"tipo_vehiculo": "CARRO", "valor": 120000}, {"tipo_vehiculo": "moto", "valor": 120000},
    {"tipo_vehiculo": "MOTO", "valor": 120000, "vigente_desde": "2020-01-01T00:00:00Z"},
])
def test_tarifa_invalida_se_rechaza_sin_crear_nada(api_y_sesion, cuerpo):
    api, session = api_y_sesion
    antes = cantidad(session)
    assert api.post("/tarifas", json=cuerpo).status_code == 422
    assert cantidad(session) == antes


def test_operador_ve_las_vigentes_pero_no_actualiza_ni_ve_el_historial(api_y_sesion):
    api, session = api_y_sesion
    crear_tarifa(session, "MOTO", 60000)
    autenticar(api, session, rol="OPERADOR")
    assert api.get("/tarifas").status_code == 200
    antes = cantidad(session)
    respuesta = api.post("/tarifas", json={"tipo_vehiculo": "MOTO", "valor": 70000})
    assert respuesta.status_code == 403 and respuesta.json() == {"detail": SIN_PERMISO}
    assert api.get("/tarifas/historial").status_code == 403
    assert cantidad(session) == antes


def test_sin_sesion_no_crea_tarifas(api_y_sesion):
    api, session = api_y_sesion
    antes = cantidad(session)
    assert api.post("/tarifas", json={"tipo_vehiculo": "MOTO", "valor": 70000},
                    headers={"Authorization": ""}).status_code == 401
    assert cantidad(session) == antes


def test_los_pagos_anteriores_conservan_su_monto(api_y_sesion):
    api, session = api_y_sesion
    crear_tarifa(session, "AUTOMOVIL", 120000)
    cliente = Cliente(**datos_cliente())
    session.add(cliente)
    session.flush()
    v = Vehiculo(placa=placa_aleatoria(), color="Rojo", modelo=2024, marca="Mazda", tipo="AUTOMOVIL",
                 cliente_id=cliente.id)
    session.add(v)
    session.flush()
    anterior = api.post("/pagos", json={"placa": v.placa, "meses": 1, "metodo": "EFECTIVO",
                                        "monto_confirmado": 120000}).json()
    assert api.post("/tarifas", json={"tipo_vehiculo": "AUTOMOVIL", "valor": 135000}).status_code == 201
    assert api.get(f"/pagos/{anterior['id']}").json()["monto"] == 120000
    nuevo = api.post("/pagos", json={"placa": v.placa, "meses": 2, "metodo": "EFECTIVO", "monto_confirmado": 270000})
    assert nuevo.status_code == 201 and nuevo.json()["valor_mensual"] == 135000 and nuevo.json()["monto"] == 270000
