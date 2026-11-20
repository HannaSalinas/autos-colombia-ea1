"""Iteración 3: resumen de recaudo (HU-33; casos RE-01 a RE-04 del plan PP-03)."""

from datetime import timedelta

from conftest import autenticar, crear_tarifa, datos_cliente, placa_aleatoria
from app.domain.reglas import hoy_bogota
from app.models import Cliente, Vehiculo
from app.services.autenticacion import SIN_PERMISO


def vehiculo(session, tipo: str) -> Vehiculo:
    cliente = Cliente(**datos_cliente())
    session.add(cliente)
    session.flush()
    v = Vehiculo(placa=placa_aleatoria(tipo), color="Azul", modelo=2023, marca="Honda", tipo=tipo,
                 cliente_id=cliente.id)
    session.add(v)
    session.flush()
    return v


def pagar(api, placa: str, meses: int, monto: int, metodo: str = "EFECTIVO", referencia: str | None = None) -> dict:
    cuerpo = {"placa": placa, "meses": meses, "metodo": metodo, "monto_confirmado": monto}
    if referencia:
        cuerpo["referencia"] = referencia
    respuesta = api.post("/pagos", json=cuerpo)
    assert respuesta.status_code == 201, respuesta.json()
    return respuesta.json()


def resumen(api, desde, hasta) -> dict:
    respuesta = api.get(f"/reportes/recaudo?desde={desde.isoformat()}&hasta={hasta.isoformat()}")
    assert respuesta.status_code == 200, respuesta.json()
    return respuesta.json()


def plano(r: dict) -> dict:
    """Totales del resumen en un diccionario simple, para comparar antes y después."""
    datos = {"validos": (r["validos"]["cantidad"], r["validos"]["total"]),
             "anulados": (r["anulados"]["cantidad"], r["anulados"]["total"])}
    datos.update({m["metodo"]: (m["cantidad"], m["total"]) for m in r["por_metodo"]})
    datos.update({t["tipo_vehiculo"]: (t["cantidad"], t["total"]) for t in r["por_tipo_vehiculo"]})
    return datos


def test_resumen_por_metodo_y_tipo_con_anulados_aparte(api_y_sesion):
    api, session = api_y_sesion
    hoy = hoy_bogota()
    crear_tarifa(session, "AUTOMOVIL", 120000)
    crear_tarifa(session, "MOTO", 60000)
    crear_tarifa(session, "CAMIONETA", 140000)
    antes = plano(resumen(api, hoy, hoy))
    pagar(api, vehiculo(session, "AUTOMOVIL").placa, 2, 240000)                           # efectivo
    pagar(api, vehiculo(session, "MOTO").placa, 1, 60000, "TRANSFERENCIA", "TRX-0001")
    pagar(api, vehiculo(session, "CAMIONETA").placa, 1, 140000, "TARJETA", "VOUCHER-1")
    anulado = pagar(api, vehiculo(session, "AUTOMOVIL").placa, 1, 120000)
    assert api.post(f"/pagos/{anulado['id']}/anular", json={"motivo": "Cobro duplicado por error"}).status_code == 200
    r = resumen(api, hoy, hoy)
    despues = plano(r)
    diferencia = {k: (despues[k][0] - antes[k][0], despues[k][1] - antes[k][1]) for k in despues}
    assert diferencia == {
        "validos": (3, 440000), "anulados": (1, 120000),
        "EFECTIVO": (1, 240000), "TRANSFERENCIA": (1, 60000), "TARJETA": (1, 140000),
        "AUTOMOVIL": (1, 240000), "MOTO": (1, 60000), "CAMIONETA": (1, 140000),
    }
    # Siempre los tres métodos y los tres tipos, en orden fijo.
    assert [m["metodo"] for m in r["por_metodo"]] == ["EFECTIVO", "TRANSFERENCIA", "TARJETA"]
    assert [t["tipo_vehiculo"] for t in r["por_tipo_vehiculo"]] == ["MOTO", "AUTOMOVIL", "CAMIONETA"]
    # Los desgloses suman el total de los válidos.
    assert sum(m["total"] for m in r["por_metodo"]) == r["validos"]["total"]
    assert sum(t["total"] for t in r["por_tipo_vehiculo"]) == r["validos"]["total"]
    assert (r["desde"], r["hasta"]) == (hoy.isoformat(), hoy.isoformat())


def test_rango_sin_pagos_da_ceros_sin_error(api_y_sesion):
    api, _ = api_y_sesion
    hoy = hoy_bogota()
    r = resumen(api, hoy - timedelta(days=9000), hoy - timedelta(days=8990))
    assert r["validos"] == {"cantidad": 0, "total": 0} and r["anulados"] == {"cantidad": 0, "total": 0}
    assert all(m["cantidad"] == 0 and m["total"] == 0 for m in r["por_metodo"] + r["por_tipo_vehiculo"])


def test_rango_invertido_y_fechas_faltantes(api_y_sesion):
    api, _ = api_y_sesion
    hoy = hoy_bogota()
    respuesta = api.get(f"/reportes/recaudo?desde={hoy.isoformat()}&hasta={(hoy - timedelta(days=1)).isoformat()}")
    assert respuesta.status_code == 422
    assert respuesta.json() == {"detail": "La fecha inicial no puede ser posterior a la fecha final."}
    assert api.get("/reportes/recaudo").status_code == 422
    assert api.get(f"/reportes/recaudo?desde={hoy.isoformat()}").status_code == 422
    assert api.get("/reportes/recaudo?desde=hoy&hasta=manana").status_code == 422


def test_operador_no_accede_al_recaudo(api_y_sesion):
    api, session = api_y_sesion
    autenticar(api, session, rol="OPERADOR")
    hoy = hoy_bogota().isoformat()
    respuesta = api.get(f"/reportes/recaudo?desde={hoy}&hasta={hoy}")
    assert respuesta.status_code == 403 and respuesta.json() == {"detail": SIN_PERMISO}
    # Sigue viendo los reportes operativos.
    assert api.get("/reportes/ocupacion").status_code == 200
    assert api.get(f"/reportes/recaudo?desde={hoy}&hasta={hoy}", headers={"Authorization": ""}).status_code == 401
