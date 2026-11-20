"""Iteración 3: concurrencia en pagos (RNF-23, HU-30 criterio 6).

Con datos confirmados (cada portería es una solicitud real con su propia transacción) que se limpian
por id. Los pagos no se pueden borrar (RNF-24, triggers de la 0010): la limpieza desactiva esos
triggers solo dentro de su propia transacción, algo que puede hacer el dueño de la base en la base de
pruebas y que la aplicación nunca hace.
"""

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event, select, text
from sqlalchemy.orm import Session

from conftest import crear_cuenta, crear_tarifa, datos_cliente, encabezado, placa_aleatoria
from app.database import get_engine
from app.domain.reglas import hoy_bogota
from app.main import app
from app.models import Cliente, CuentaUsuario, Mensualidad, Operador, Pago, Tarifa, Vehiculo

pytestmark = pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Requiere PostgreSQL local.")


@pytest.fixture
def datos():
    """Un automóvil sin mensualidad, su tarifa y dos cuentas: una por portería (Operador) y la
    del Administrador, que es quien anula."""
    engine = get_engine()
    with Session(engine) as s, s.begin():
        cliente = Cliente(**datos_cliente())
        s.add(cliente)
        s.flush()
        vehiculo = Vehiculo(placa=placa_aleatoria(), color="Gris", modelo=2024, marca="Kia", tipo="AUTOMOVIL",
                            cliente_id=cliente.id)
        s.add(vehiculo)
        s.flush()
        # Si otra prueba dejó una tarifa de AUTOMOVIL confirmada, esta (más reciente) es la vigente.
        tarifa = crear_tarifa(s, "AUTOMOVIL", 120000)
        cuentas = [crear_cuenta(s, rol="OPERADOR"), crear_cuenta(s, rol="OPERADOR"), crear_cuenta(s)]
        d = {"vehiculo": vehiculo.id, "placa": vehiculo.placa, "cliente": cliente.id, "tarifa": tarifa.id,
             "cuentas": [c.id for c in cuentas], "personas": [c.operador_id for c in cuentas],
             "auth": [encabezado(c) for c in cuentas]}
    try:
        yield d
    finally:
        with Session(engine) as s, s.begin():
            # Solo en la limpieza de la base de pruebas: los triggers vuelven a quedar activos al
            # confirmar esta misma transacción (ALTER TABLE es transaccional en PostgreSQL).
            for tabla, trigger in (("pago", "pago_sin_cambios"), ("mensualidad", "mensualidad_pagada_sin_cambios"),
                                   ("tarifa", "tarifa_sin_cambios")):
                s.execute(text(f"ALTER TABLE {tabla} DISABLE TRIGGER {trigger}"))
            pagos = select(Mensualidad.pago_id).where(Mensualidad.vehiculo_id == d["vehiculo"])
            ids_pagos = list(s.scalars(pagos))
            s.execute(delete(Mensualidad).where(Mensualidad.vehiculo_id == d["vehiculo"]))
            s.execute(delete(Pago).where(Pago.id.in_([i for i in ids_pagos if i is not None])))
            s.execute(delete(Tarifa).where(Tarifa.id == d["tarifa"]))
            s.execute(delete(Vehiculo).where(Vehiculo.id == d["vehiculo"]))
            s.execute(delete(Cliente).where(Cliente.id == d["cliente"]))
            s.execute(delete(CuentaUsuario).where(CuentaUsuario.id.in_(d["cuentas"])))
            s.execute(delete(Operador).where(Operador.id.in_(d["personas"])))
            for tabla, trigger in (("pago", "pago_sin_cambios"), ("mensualidad", "mensualidad_pagada_sin_cambios"),
                                   ("tarifa", "tarifa_sin_cambios")):
                s.execute(text(f"ALTER TABLE {tabla} ENABLE TRIGGER {trigger}"))
        with engine.connect() as c:
            assert c.scalar(text("SELECT count(*) FROM pg_trigger WHERE tgname IN ('pago_sin_cambios', "
                                 "'mensualidad_pagada_sin_cambios', 'tarifa_sin_cambios') AND tgenabled = 'O'")) == 3


def carrera(solicitudes):
    """Envía dos solicitudes a la vez; ambas esperan juntas justo antes de bloquear la fila del vehículo."""
    barrera = Barrier(2, timeout=15)
    esperado = threading.local()

    def sincronizar(conn, cursor, statement, parameters, context, executemany):
        if "FROM vehiculo" in statement and "FOR UPDATE" in statement and not getattr(esperado, "listo", False):
            esperado.listo = True
            barrera.wait()

    def enviar(solicitud):
        ruta, cuerpo, encabezados = solicitud
        with TestClient(app, headers=encabezados) as client:
            return client.post(ruta, json=cuerpo)

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", sincronizar)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(enviar, solicitudes))
    finally:
        event.remove(engine, "before_cursor_execute", sincronizar)


def periodos(d) -> list[tuple[date, date, str | None]]:
    with Session(get_engine()) as s:
        return [tuple(f) for f in s.execute(
            select(Mensualidad.fecha_inicio, Mensualidad.fecha_fin, Mensualidad.pago_estado)
            .where(Mensualidad.vehiculo_id == d["vehiculo"]).order_by(Mensualidad.fecha_inicio, Mensualidad.id))]


def pago(d, meses: int = 1) -> dict:
    return {"placa": d["placa"], "meses": meses, "metodo": "EFECTIVO", "monto_confirmado": 120000 * meses}


def test_dos_pagos_simultaneos_del_mismo_vehiculo_dan_periodos_consecutivos(datos):
    d = datos
    respuestas = carrera([("/pagos", pago(d), d["auth"][0]), ("/pagos", pago(d), d["auth"][1])])
    assert [r.status_code for r in respuestas] == [201, 201], [r.json() for r in respuestas]
    (i1, f1, e1), (i2, f2, e2) = periodos(d)
    hoy = hoy_bogota()
    assert i1 == hoy and i2 == f1 + timedelta(days=1)          # consecutivos, sin superposición ni hueco
    assert e1 == e2 == "VALIDO"
    comprobantes = {r.json()["comprobante"] for r in respuestas}
    assert len(comprobantes) == 2                               # comprobante único
    # Cada portería queda como responsable de su propio pago.
    responsables = {r.json()["registrado_por"].split("(")[1].rstrip(")") for r in respuestas}
    assert len(responsables) == 2


def test_pago_y_anulacion_simultaneos_no_dejan_un_estado_incoherente(datos):
    d = datos
    with TestClient(app, headers=d["auth"][2]) as admin:
        primero = admin.post("/pagos", json=pago(d)).json()
    respuestas = carrera([("/pagos", pago(d), d["auth"][0]),
                          (f"/pagos/{primero['id']}/anular", {"motivo": "Cobro registrado por error"}, d["auth"][2])])
    registro, anulacion = respuestas
    assert registro.status_code == 201
    filas = periodos(d)
    if anulacion.status_code == 200:
        # La anulación ganó el bloqueo: el pago nuevo ya no ve el periodo anulado y empieza hoy.
        assert [e for *_, e in filas] == ["ANULADO", "VALIDO"]
        assert filas[1][0] == hoy_bogota()
    else:
        # El pago ganó el bloqueo: el primero dejó de ser el último periodo y ya no se puede anular.
        assert anulacion.status_code == 409 and "último periodo" in anulacion.json()["detail"]
        assert [e for *_, e in filas] == ["VALIDO", "VALIDO"]
        assert filas[1][0] == filas[0][1] + timedelta(days=1)
    validos = [(i, f) for i, f, e in filas if e == "VALIDO"]
    assert all(a[1] < b[0] for a, b in zip(validos, validos[1:]))   # nunca se superponen
