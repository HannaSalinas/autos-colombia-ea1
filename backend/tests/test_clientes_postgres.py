"""Iteración 3: registrar y consultar clientes (HU-28; casos CL-01 a CL-06 del plan PP-03)."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.orm import Session

from conftest import autenticar, crear_cuenta, datos_cliente, encabezado, placa_aleatoria
from app.database import get_engine
from app.main import app
from app.models import Cliente, CuentaUsuario, Operador, Vehiculo
from app.services.autenticacion import SIN_PERMISO


def nuevo(**cambios) -> dict:
    """Cuerpo válido de POST /clientes, con un documento que no choca con los existentes."""
    datos = datos_cliente(**cambios)
    return {"tipo_documento": "CC", "documento": datos["documento"], "nombre": datos["nombre"],
            "telefono": datos["telefono"], "correo": "ana@correo.com", **cambios}


def cantidad(session, documento: str) -> int:
    return session.scalar(select(func.count()).select_from(Cliente).where(func.upper(Cliente.documento) ==
                                                                          documento.upper()))


def test_registrar_cliente_y_encontrarlo(api_y_sesion):
    api, session = api_y_sesion
    cuerpo = nuevo(nombre="Ana Restrepo Prueba", documento=" t1020304050 ")
    respuesta = api.post("/clientes", json=cuerpo)
    assert respuesta.status_code == 201, respuesta.json()
    cliente = respuesta.json()
    assert cliente["documento"] == "T1020304050"            # sin espacios exteriores y en mayúsculas
    assert (cliente["tipo_documento"], cliente["nombre"], cliente["correo"]) == ("CC", "Ana Restrepo Prueba",
                                                                                "ana@correo.com")
    # D18: el propio registro guarda quién y cuándo.
    assert "(prueba." in cliente["registrado_por"] and cliente["registrado_en"]
    assert cliente["vehiculos"] == []
    assert cantidad(session, "T1020304050") == 1
    assert api.get(f"/clientes/{cliente['id']}").json() == cliente
    encontrados = api.get("/clientes?buscar=restrepo prueba").json()["items"]
    assert [c["id"] for c in encontrados] == [cliente["id"]]


@pytest.mark.parametrize("cambios", [
    {"documento": "1234"}, {"documento": "1" * 16}, {"documento": "1.234.567"}, {"documento": "   "},
    {"nombre": "Al"}, {"nombre": "a" * 81}, {"nombre": "     "},
    {"telefono": "300111223"}, {"telefono": "30011122334"}, {"telefono": "300111223a"},
    {"correo": "ana@"}, {"correo": "texto sin arroba"},
    {"tipo_documento": "TI"}, {"tipo_documento": None}, {"documento": 1234567},
    {"registrado_por_cuenta_id": 1},
])
def test_datos_invalidos_se_rechazan_sin_crear_nada(api_y_sesion, cambios):
    api, session = api_y_sesion
    antes = session.scalar(select(func.count()).select_from(Cliente))
    respuesta = api.post("/clientes", json=nuevo(**cambios))
    assert respuesta.status_code == 422
    assert session.scalar(select(func.count()).select_from(Cliente)) == antes


@pytest.mark.parametrize("cambios", [
    {"documento": "A2345"}, {"documento": "B" + "1" * 14}, {"nombre": "Ana"}, {"nombre": "a" * 80},
    {"telefono": "3001112233"}, {"correo": None}, {"correo": ""}, {"tipo_documento": "CE"}, {"tipo_documento": "PA"},
])
def test_limites_validos_se_aceptan(api_y_sesion, cambios):
    api, _ = api_y_sesion
    respuesta = api.post("/clientes", json=nuevo(**cambios))
    assert respuesta.status_code == 201, respuesta.json()
    if "correo" in cambios:
        assert respuesta.json()["correo"] is None


def test_documento_duplicado(api_y_sesion):
    api, session = api_y_sesion
    cuerpo = nuevo()
    assert api.post("/clientes", json=cuerpo).status_code == 201
    for repetido in (cuerpo, {**cuerpo, "documento": cuerpo["documento"].lower(), "nombre": "Otra persona"}):
        respuesta = api.post("/clientes", json=repetido)
        assert respuesta.status_code == 409
        assert respuesta.json() == {"detail": f"Ya existe un cliente con el documento CC {cuerpo['documento']}."}
    assert cantidad(session, cuerpo["documento"]) == 1
    # Mismo número con otro tipo de documento: es otro documento (único por tipo y número).
    assert api.post("/clientes", json={**cuerpo, "tipo_documento": "PA"}).status_code == 201


def test_buscar_por_nombre_o_documento_con_sus_vehiculos(api_y_sesion):
    api, session = api_y_sesion
    cliente = api.post("/clientes", json=nuevo(nombre="Jorge Mesa Búsqueda")).json()
    v = Vehiculo(placa=placa_aleatoria(), color="Plata", modelo=2024, marca="Chevrolet", tipo="AUTOMOVIL",
                 cliente_id=cliente["id"])
    session.add(v)
    session.flush()
    por_nombre = api.get("/clientes?buscar=MESA BÚSQUEDA").json()["items"]
    assert [c["id"] for c in por_nombre] == [cliente["id"]]
    assert por_nombre[0]["vehiculos"] == [{"id": v.id, "placa": v.placa, "tipo": "AUTOMOVIL"}]
    por_documento = api.get(f"/clientes?buscar={cliente['documento'][2:9]}").json()["items"]
    assert cliente["id"] in [c["id"] for c in por_documento]
    assert api.get("/clientes?buscar=zzz-sin-coincidencias-%_").json() == {"items": [], "total": 0, "offset": 0,
                                                                            "limit": 20}


def test_operador_consulta_pero_no_registra(api_y_sesion):
    api, session = api_y_sesion
    cliente = api.post("/clientes", json=nuevo(nombre="Cliente Visible Operador")).json()
    autenticar(api, session, rol="OPERADOR")
    assert [c["id"] for c in api.get("/clientes?buscar=Visible Operador").json()["items"]] == [cliente["id"]]
    assert api.get(f"/clientes/{cliente['id']}").status_code == 200
    cuerpo = nuevo()
    respuesta = api.post("/clientes", json=cuerpo)
    assert respuesta.status_code == 403 and respuesta.json() == {"detail": SIN_PERMISO}
    assert cantidad(session, cuerpo["documento"]) == 0


def test_sin_sesion_no_registra(api_y_sesion):
    api, session = api_y_sesion
    cuerpo = nuevo()
    assert api.post("/clientes", json=cuerpo, headers={"Authorization": ""}).status_code == 401
    assert cantidad(session, cuerpo["documento"]) == 0


# --- CL-04: dos registros simultáneos del mismo documento (datos confirmados, limpieza por id) ---

@pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Requiere PostgreSQL local.")
def test_dos_registros_simultaneos_del_mismo_documento_dejan_uno():
    engine = get_engine()
    with Session(engine) as s, s.begin():
        cuentas = [crear_cuenta(s), crear_cuenta(s)]
        ids_cuentas, personas = [c.id for c in cuentas], [c.operador_id for c in cuentas]
        encabezados = [encabezado(c) for c in cuentas]
    cuerpo = nuevo()
    barrera, esperado = Barrier(2, timeout=15), threading.local()

    def sincronizar(conn, cursor, statement, parameters, context, executemany):
        # Ambos esperan juntos justo antes del INSERT: los dos ya pasaron la revisión previa.
        if statement.startswith("INSERT INTO cliente") and not getattr(esperado, "listo", False):
            esperado.listo = True
            barrera.wait()

    def enviar(headers):
        with TestClient(app, headers=headers) as client:
            return client.post("/clientes", json=cuerpo)

    event.listen(engine, "before_cursor_execute", sincronizar)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            respuestas = list(pool.map(enviar, encabezados))
    finally:
        event.remove(engine, "before_cursor_execute", sincronizar)
        try:
            assert sorted(r.status_code for r in respuestas) == [201, 409]
            conflicto = next(r for r in respuestas if r.status_code == 409).json()
            assert conflicto == {"detail": f"Ya existe un cliente con el documento CC {cuerpo['documento']}."}
            with engine.connect() as c:
                assert c.scalar(text("SELECT count(*) FROM cliente WHERE documento = :d"),
                                {"d": cuerpo["documento"]}) == 1
        finally:
            with Session(engine) as s, s.begin():
                s.execute(delete(Cliente).where(Cliente.documento == cuerpo["documento"]))
                s.execute(delete(CuentaUsuario).where(CuentaUsuario.id.in_(ids_cuentas)))
                s.execute(delete(Operador).where(Operador.id.in_(personas)))
