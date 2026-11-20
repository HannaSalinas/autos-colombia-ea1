"""Iteración 3: un periodo anulado deja de habilitar la entrada (RF-38, HU-29 criterio 3, HU-32 criterio 3).

La regla de entrada de la Iteración 1 no cambia: entra si tiene un periodo vigente que no esté anulado.
"""

from datetime import timedelta

from conftest import codigos_celda_libres, crear_cuenta, datos_cliente, periodo_pagado, placa_aleatoria
from app.domain.reglas import fin_de_mensualidad, hoy_bogota
from app.models import Celda, Cliente, Mensualidad, Vehiculo


def vehiculo(session) -> Vehiculo:
    cliente = Cliente(**datos_cliente())
    session.add(cliente)
    session.flush()
    v = Vehiculo(placa=placa_aleatoria(), color="Gris", modelo=2024, marca="Kia", tipo="AUTOMOVIL",
                 cliente_id=cliente.id)
    session.add(v)
    session.flush()
    return v


def test_periodo_anulado_no_deja_entrar(api_y_sesion):
    api, session = api_y_sesion
    hoy, cuenta = hoy_bogota(), crear_cuenta(session).id
    v = vehiculo(session)
    periodo_pagado(session, v, hoy - timedelta(days=3), hoy + timedelta(days=26), cuenta, anulado=True)
    respuesta = api.post("/estancias/entrada", json={"placa": v.placa})
    assert respuesta.status_code == 409
    assert respuesta.json() == {"detail": "El vehículo no tiene mensualidad vigente. No puede ingresar."}
    detalle = api.get(f"/vehiculos/{v.id}").json()
    assert detalle["mensualidad_vigente"] is False and detalle["mensualidad_hasta"] is None


def test_periodo_pagado_y_valido_deja_entrar(api_y_sesion):
    api, session = api_y_sesion
    hoy, cuenta = hoy_bogota(), crear_cuenta(session).id
    v = vehiculo(session)
    periodo_pagado(session, v, hoy, hoy + timedelta(days=29), cuenta)
    session.add(Celda(codigo=codigos_celda_libres(session, "CARRO")[0], tipo="CARRO"))   # la base de pruebas no tiene celdas
    session.flush()
    assert api.get(f"/vehiculos/{v.id}").json()["mensualidad_vigente"] is True
    respuesta = api.post("/estancias/entrada", json={"placa": v.placa})
    assert respuesta.status_code == 201, respuesta.json()


def test_periodo_futuro_anulado_no_cuenta_como_proximo(api_y_sesion):
    api, session = api_y_sesion
    hoy, cuenta = hoy_bogota(), crear_cuenta(session).id
    v = vehiculo(session)
    # Periodo antiguo (sin pago, D10) vigente, más uno pagado hacia adelante que se anuló.
    inicio = hoy - timedelta(days=10)
    fin = fin_de_mensualidad(inicio)
    session.add(Mensualidad(vehiculo_id=v.id, fecha_inicio=inicio, fecha_fin=fin))
    session.flush()
    periodo_pagado(session, v, fin + timedelta(days=1), fin + timedelta(days=30), cuenta, anulado=True)
    detalle = api.get(f"/vehiculos/{v.id}").json()
    assert detalle["mensualidad_vigente"] is True and detalle["mensualidad_hasta"] == fin.isoformat()
    assert detalle["mensualidad_proxima"] is None


def test_historial_de_mensualidades_muestra_comprobante_y_anulados(api_y_sesion):
    api, session = api_y_sesion
    hoy, cuenta = hoy_bogota(), crear_cuenta(session).id
    v = vehiculo(session)
    session.add(Mensualidad(vehiculo_id=v.id, fecha_inicio=hoy - timedelta(days=60), fecha_fin=hoy - timedelta(days=30)))
    pago, _ = periodo_pagado(session, v, hoy, hoy + timedelta(days=29), cuenta, anulado=True)
    filas = api.get(f"/vehiculos/{v.id}/mensualidades").json()
    assert [(f["comprobante"], f["pago_estado"], f["vigente"]) for f in filas] == [
        (pago.comprobante, "ANULADO", False),     # el más reciente primero; anulado: no vigente
        (None, None, False),                      # periodo anterior a la Iteración 3, sin pago
    ]
