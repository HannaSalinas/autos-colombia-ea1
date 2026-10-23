"""Integración Fase 1: clientes, reglas de vehículo y estado de mensualidad (PostgreSQL real, con rollback)."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from conftest import placa_aleatoria
from app.domain.reglas import fin_de_mensualidad, hoy_bogota
from app.models import Celda, Cliente, Estancia, Mensualidad, Operador


def nuevo_cliente(session, correo=None) -> Cliente:
    cliente = Cliente(documento=f"TEST-{uuid4().hex}", nombre="Cliente de prueba", telefono="3000000000",
                      correo=correo)
    session.add(cliente)
    session.flush()
    return cliente


def carro(cliente_id, **cambios):
    return {"placa": placa_aleatoria(), "color": "Rojo", "modelo": 2024, "marca": "Mazda",
            "tipo": "AUTOMOVIL", "cliente_id": cliente_id, **cambios}


def test_crear_vehiculo_normaliza_y_devuelve_detalle(api_y_sesion):
    api, session = api_y_sesion
    cliente = nuevo_cliente(session)
    placa = placa_aleatoria()
    creado = api.post("/vehiculos", json=carro(cliente.id, placa=f" {placa[:3].lower()} - {placa[3:]} "))
    assert creado.status_code == 201
    cuerpo = creado.json()
    assert cuerpo["placa"] == placa
    assert cuerpo["cliente_id"] == cliente.id and cuerpo["cliente_nombre"] == "Cliente de prueba"
    assert cuerpo["mensualidad_vigente"] is False and cuerpo["mensualidad_hasta"] is None
    moto = api.post("/vehiculos", json=carro(cliente.id, placa=placa_aleatoria("MOTO"), tipo="MOTO"))
    assert moto.status_code == 201


@pytest.mark.parametrize("cambios", [
    {"tipo": "MOTO"},                       # placa de carro en una moto
    {"placa": "ABC12D"},                    # placa de moto en un carro
    {"placa": "AB1234"},
    {"modelo": 1899},
    {"cliente_id": None},
    {"cliente_id": "1"},
])
def test_crear_vehiculo_rechaza_datos_invalidos(api_y_sesion, cambios):
    api, session = api_y_sesion
    cliente = nuevo_cliente(session)
    assert api.post("/vehiculos", json={**carro(cliente.id), **cambios}).status_code == 422


def test_modelo_limite_superior_es_anio_actual_mas_uno(api_y_sesion):
    api, session = api_y_sesion
    cliente = nuevo_cliente(session)
    anio = hoy_bogota().year
    assert api.post("/vehiculos", json=carro(cliente.id, modelo=anio + 1)).status_code == 201
    assert api.post("/vehiculos", json=carro(cliente.id, modelo=anio + 2)).status_code == 422
    assert api.post("/vehiculos", json=carro(cliente.id, modelo=1900)).status_code == 201


def test_cliente_inexistente(api_y_sesion):
    api, session = api_y_sesion
    assert api.post("/vehiculos", json=carro(9223372036854775807)).status_code == 404
    vehiculo = api.post("/vehiculos", json=carro(nuevo_cliente(session).id)).json()
    assert api.patch(f"/vehiculos/{vehiculo['id']}", json={"cliente_id": 9223372036854775807}).status_code == 404


def test_patch_valida_placa_con_el_tipo_final(api_y_sesion):
    api, session = api_y_sesion
    vehiculo = api.post("/vehiculos", json=carro(nuevo_cliente(session).id)).json()
    url = f"/vehiculos/{vehiculo['id']}"
    rechazo = api.patch(url, json={"tipo": "MOTO"})
    assert rechazo.status_code == 422 and "moto" in rechazo.json()["detail"]
    assert api.get(url).json()["tipo"] == "AUTOMOVIL"
    moto = placa_aleatoria("MOTO")
    cambio = api.patch(url, json={"tipo": "MOTO", "placa": moto.lower()})
    assert cambio.status_code == 200 and cambio.json()["placa"] == moto
    otro = nuevo_cliente(session)
    assert api.patch(url, json={"cliente_id": otro.id}).json()["cliente_id"] == otro.id


def test_no_cambia_tipo_de_vehiculo_dentro(api_y_sesion):
    api, session = api_y_sesion
    vehiculo = api.post("/vehiculos", json=carro(nuevo_cliente(session).id)).json()
    celda = Celda(codigo=f"TEST-{uuid4().hex}", tipo="CARRO")
    operador = Operador(nombre="Prueba", telefono="001")
    session.add_all([celda, operador])
    session.flush()
    session.add(Estancia(vehiculo_id=vehiculo["id"], celda_id=celda.id, operador_entrada_id=operador.id))
    session.flush()
    url = f"/vehiculos/{vehiculo['id']}"
    respuesta = api.patch(url, json={"tipo": "CAMIONETA"})
    assert respuesta.status_code == 409 and "dentro" in respuesta.json()["detail"]
    assert api.get(url).json()["tipo"] == "AUTOMOVIL"
    # Otros datos sí se pueden corregir, y enviar el mismo tipo no es un cambio.
    assert api.patch(url, json={"color": "Negro", "tipo": "AUTOMOVIL"}).status_code == 200


@pytest.mark.parametrize("dias_inicio,dias_fin,vigente", [
    (-10, None, True),   # pagó hace 10 días: vence en un mes
    (None, 0, True),     # vence hoy: todavía puede entrar
    (None, -1, False),   # venció ayer
    (1, None, False),    # empieza mañana
])
def test_estado_de_mensualidad_en_listado(api_y_sesion, dias_inicio, dias_fin, vigente):
    api, session = api_y_sesion
    hoy = hoy_bogota()
    vehiculo = api.post("/vehiculos", json=carro(nuevo_cliente(session).id)).json()
    if dias_inicio is not None:
        inicio = hoy + timedelta(days=dias_inicio)
        fin = fin_de_mensualidad(inicio)
    else:
        fin = hoy + timedelta(days=dias_fin)
        inicio = fin - timedelta(days=30)
    session.add(Mensualidad(vehiculo_id=vehiculo["id"], fecha_inicio=inicio, fecha_fin=fin))
    session.flush()
    detalle = api.get(f"/vehiculos/{vehiculo['id']}").json()
    assert detalle["mensualidad_vigente"] is vigente
    assert detalle["mensualidad_hasta"] == (None if dias_inicio == 1 else fin.isoformat())
    historial = api.get(f"/vehiculos/{vehiculo['id']}/mensualidades").json()
    assert [(m["fecha_inicio"], m["vigente"]) for m in historial] == [(inicio.isoformat(), vigente)]


def test_renovacion_muestra_la_fecha_mas_lejana(api_y_sesion):
    api, session = api_y_sesion
    hoy = hoy_bogota()
    vehiculo = api.post("/vehiculos", json=carro(nuevo_cliente(session).id)).json()
    primera = hoy - timedelta(days=40)
    segunda = fin_de_mensualidad(primera)
    session.add_all([
        Mensualidad(vehiculo_id=vehiculo["id"], fecha_inicio=primera, fecha_fin=segunda),
        Mensualidad(vehiculo_id=vehiculo["id"], fecha_inicio=segunda, fecha_fin=fin_de_mensualidad(segunda)),
    ])
    session.flush()
    detalle = api.get(f"/vehiculos/{vehiculo['id']}").json()
    assert detalle["mensualidad_vigente"] is True
    assert detalle["mensualidad_hasta"] == fin_de_mensualidad(segunda).isoformat()
    assert len(api.get(f"/vehiculos/{vehiculo['id']}/mensualidades").json()) == 2
    # Tener mensualidades impide borrar el vehículo: el historial no se pierde.
    assert api.delete(f"/vehiculos/{vehiculo['id']}").status_code == 409
    assert api.get("/vehiculos/9223372036854775807/mensualidades").status_code == 404


def test_api_de_clientes_solo_lectura(api_y_sesion):
    api, session = api_y_sesion
    con_correo = nuevo_cliente(session, correo="prueba@example.com")
    sin_correo = nuevo_cliente(session)
    for _ in range(2):
        api.post("/vehiculos", json=carro(con_correo.id))
    pagina = api.get("/clientes?limit=100")
    assert pagina.status_code == 200 and pagina.json()["total"] >= 2
    detalle = api.get(f"/clientes/{con_correo.id}").json()
    assert detalle["correo"] == "prueba@example.com"
    assert api.get(f"/clientes/{sin_correo.id}").json()["correo"] is None
    vehiculos = api.get(f"/clientes/{con_correo.id}/vehiculos").json()
    assert len(vehiculos) == 2 and {v["cliente_id"] for v in vehiculos} == {con_correo.id}
    assert api.get(f"/clientes/{sin_correo.id}/vehiculos").json() == []
    assert api.get("/clientes/9223372036854775807").status_code == 404
    assert api.get("/clientes/0").status_code == 422
    # No hay escritura de clientes en esta iteración.
    assert api.post("/clientes", json={}).status_code == 405


@pytest.mark.parametrize("sql", [
    # La base rechaza datos inválidos aunque alguien se salte la API.
    "INSERT INTO vehiculo (placa, color, modelo, marca, tipo, cliente_id) VALUES (:carro, 'R', 2020, 'M', 'MOTO', :c)",
    "INSERT INTO vehiculo (placa, color, modelo, marca, tipo, cliente_id) VALUES (:moto, 'R', 2020, 'M', 'AUTOMOVIL', :c)",
    "INSERT INTO vehiculo (placa, color, modelo, marca, tipo, cliente_id) VALUES (:carro, 'R', 1899, 'M', 'AUTOMOVIL', :c)",
    "INSERT INTO cliente (documento, nombre, telefono, correo) VALUES ('X' || :c, 'N', 'T', 'sin-arroba')",
    "INSERT INTO cliente (documento, nombre, telefono) SELECT documento, 'N', 'T' FROM cliente WHERE id = :c",
])
def test_restricciones_de_la_base(api_y_sesion, sql):
    _, session = api_y_sesion
    cliente = nuevo_cliente(session)
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(text(sql), {"c": cliente.id, "carro": placa_aleatoria(), "moto": placa_aleatoria("MOTO")})
