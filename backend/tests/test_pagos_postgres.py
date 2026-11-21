"""Iteración 3: estado de la mensualidad, registrar, consultar y anular pagos (HU-29 a HU-32).

Con PostgreSQL real y rollback (fixture api_y_sesion). Las tarifas se crean en cada prueba: la base de
pruebas no tiene semillas. La concurrencia está en test_pagos_concurrencia_postgres.py.
"""

from datetime import date, timedelta

import pytest

from conftest import (
    autenticar, codigos_celda_libres, crear_cuenta, crear_tarifa, datos_cliente, periodo_pagado, placa_aleatoria,
)
from app.domain.pagos import fin_de_periodo, tope_de_adelanto
from app.domain.reglas import hoy_bogota
from app.models import Celda, Cliente, Mensualidad, Pago, Vehiculo
from app.services.autenticacion import SIN_PERMISO


def vehiculo(session, tipo: str = "AUTOMOVIL") -> Vehiculo:
    cliente = Cliente(**datos_cliente(nombre="Paola Ríos"))
    session.add(cliente)
    session.flush()
    v = Vehiculo(placa=placa_aleatoria(tipo), color="Verde", modelo=2025, marca="Kia", tipo=tipo,
                 cliente_id=cliente.id)
    session.add(v)
    session.flush()
    return v


def periodo_antiguo(session, v: Vehiculo, inicio: date, fin: date) -> None:
    """Periodo de las iteraciones 1 y 2: sin pago (D10)."""
    session.add(Mensualidad(vehiculo_id=v.id, fecha_inicio=inicio, fecha_fin=fin))
    session.flush()


def pagar(api, placa: str, meses: int = 1, metodo: str = "EFECTIVO", referencia: str | None = None, **extra):
    """Como la pantalla: pide el resumen (cotización) y confirma con el monto que vio."""
    cotizacion = api.get(f"/pagos/cotizacion?placa={placa}&meses={meses}")
    assert cotizacion.status_code == 200, cotizacion.json()
    cuerpo = {"placa": placa, "meses": meses, "metodo": metodo, "monto_confirmado": cotizacion.json()["monto"],
              **extra}
    if referencia is not None:
        cuerpo["referencia"] = referencia
    return api.post("/pagos", json=cuerpo)


# --- HU-29 Consultar estado de la mensualidad ---

def test_estado_sin_mensualidad(api_y_sesion):
    api, session = api_y_sesion
    v, hoy = vehiculo(session), hoy_bogota()
    tarifa = crear_tarifa(session, "AUTOMOVIL", 120000)
    estado = api.get(f"/pagos/estado/{v.placa}").json()
    assert estado["estado"] == "SIN_MENSUALIDAD" and estado["periodo_actual"] is None
    assert estado["periodos_futuros"] == [] and estado["vence"] is None and estado["dias_restantes"] is None
    assert estado["periodos_anulados"] == []
    assert estado["cliente"]["nombre"] == "Paola Ríos" and estado["cliente"]["tipo_documento"] == "CC"
    assert estado["placa"] == v.placa and estado["tipo_vehiculo"] == "AUTOMOVIL"
    assert estado["inicio_nuevo_periodo"] == hoy.isoformat()
    assert estado["fin_maximo"] == tope_de_adelanto(hoy).isoformat()
    assert estado["tarifa"] == {"id": tarifa.id, "tipo_vehiculo": "AUTOMOVIL", "valor": 120000}


def test_estado_vigente_con_dias_restantes_y_periodos_hacia_adelante(api_y_sesion):
    api, session = api_y_sesion
    v, hoy = vehiculo(session), hoy_bogota()
    periodo_antiguo(session, v, hoy - timedelta(days=10), hoy + timedelta(days=5))
    pago, _ = periodo_pagado(session, v, hoy + timedelta(days=6), hoy + timedelta(days=35), crear_cuenta(session).id)
    estado = api.get(f"/pagos/estado/{v.placa}").json()
    assert estado["estado"] == "VIGENTE"
    assert estado["periodo_actual"] == {"fecha_inicio": (hoy - timedelta(days=10)).isoformat(),
                                        "fecha_fin": (hoy + timedelta(days=5)).isoformat(), "comprobante": None}
    assert estado["periodos_futuros"] == [{"fecha_inicio": (hoy + timedelta(days=6)).isoformat(),
                                           "fecha_fin": (hoy + timedelta(days=35)).isoformat(),
                                           "comprobante": pago.comprobante}]
    # Encadenados: vence al final del último y los días cuentan hasta allí.
    assert estado["vence"] == (hoy + timedelta(days=35)).isoformat() and estado["dias_restantes"] == 35
    assert estado["inicio_nuevo_periodo"] == (hoy + timedelta(days=36)).isoformat()
    assert estado["tarifa"]["valor"] == 120000     # la tarifa con la que se preparó el pago


def test_estado_vence_hoy_vencida_y_pagada_a_futuro(api_y_sesion):
    api, session = api_y_sesion
    hoy = hoy_bogota()
    vence_hoy, vencida, futura = vehiculo(session), vehiculo(session, "MOTO"), vehiculo(session, "CAMIONETA")
    periodo_antiguo(session, vence_hoy, hoy - timedelta(days=30), hoy)
    periodo_antiguo(session, vencida, hoy - timedelta(days=35), hoy - timedelta(days=5))
    periodo_antiguo(session, futura, hoy + timedelta(days=1), hoy + timedelta(days=31))
    e = api.get(f"/pagos/estado/{vence_hoy.placa}").json()
    assert (e["estado"], e["dias_restantes"], e["inicio_nuevo_periodo"]) == (
        "VIGENTE", 0, (hoy + timedelta(days=1)).isoformat())
    e = api.get(f"/pagos/estado/{vencida.placa}").json()
    assert (e["estado"], e["vence"], e["inicio_nuevo_periodo"]) == (
        "VENCIDA", (hoy - timedelta(days=5)).isoformat(), hoy.isoformat())
    e = api.get(f"/pagos/estado/{futura.placa}").json()
    assert e["estado"] == "PAGADA_A_FUTURO" and e["periodo_actual"] is None and len(e["periodos_futuros"]) == 1


def test_estado_ignora_periodos_anulados_pero_los_muestra_marcados(api_y_sesion):
    api, session = api_y_sesion
    v, hoy = vehiculo(session), hoy_bogota()
    pago, _ = periodo_pagado(session, v, hoy - timedelta(days=2), hoy + timedelta(days=27), crear_cuenta(session).id,
                             anulado=True)
    estado = api.get(f"/pagos/estado/{v.placa}").json()
    assert estado["estado"] == "SIN_MENSUALIDAD" and estado["periodo_actual"] is None
    # ME-04: el periodo anulado aparece aparte, marcado como anulado, y no cuenta para el estado.
    assert estado["periodos_anulados"] == [{"fecha_inicio": (hoy - timedelta(days=2)).isoformat(),
                                            "fecha_fin": (hoy + timedelta(days=27)).isoformat(),
                                            "comprobante": pago.comprobante}]
    assert estado["inicio_nuevo_periodo"] == hoy.isoformat()


def test_estado_placa_normalizada_e_inexistente(api_y_sesion):
    api, session = api_y_sesion
    v = vehiculo(session)
    assert api.get(f"/pagos/estado/ {v.placa[:3].lower()}-{v.placa[3:]} ").json()["placa"] == v.placa
    respuesta = api.get("/pagos/estado/ZZZ999")
    assert respuesta.status_code == 404 and respuesta.json() == {"detail": "Vehículo no encontrado."}


# --- HU-30 Registrar pago ---

def test_registrar_pago_sin_mensualidad_empieza_hoy_y_genera_comprobante(api_y_sesion):
    api, session = api_y_sesion
    v, hoy = vehiculo(session), hoy_bogota()
    crear_tarifa(session, "AUTOMOVIL", 120000)
    pagos_antes = session.query(Pago).count()
    cotizacion = api.get(f"/pagos/cotizacion?placa={v.placa}&meses=3").json()
    assert cotizacion == {"placa": v.placa, "cliente_nombre": "Paola Ríos", "tipo_vehiculo": "AUTOMOVIL", "meses": 3,
                          "fecha_inicio": hoy.isoformat(), "fecha_fin": fin_de_periodo(hoy, 3).isoformat(),
                          "tarifa_id": cotizacion["tarifa_id"], "valor_mensual": 120000, "monto": 360000}
    assert session.query(Pago).count() == pagos_antes   # la cotización no guarda nada
    respuesta = pagar(api, v.placa, 3, "TRANSFERENCIA", " TRX-2026-01 ")
    assert respuesta.status_code == 201, respuesta.json()
    pago = respuesta.json()
    assert pago["comprobante"].startswith("RC-") and len(pago["comprobante"]) == 9
    assert (pago["fecha_inicio"], pago["fecha_fin"]) == (hoy.isoformat(), fin_de_periodo(hoy, 3).isoformat())
    assert (pago["meses"], pago["valor_mensual"], pago["monto"]) == (3, 120000, 360000)
    assert (pago["metodo"], pago["referencia"], pago["estado"]) == ("TRANSFERENCIA", "TRX-2026-01", "VALIDO")
    assert pago["placa"] == v.placa and pago["cliente_nombre"] == "Paola Ríos" and pago["anulable"] is True
    # Responsable: la cuenta de la sesión, "Nombre (usuario)".
    assert pago["registrado_por"].endswith(")") and "(prueba." in pago["registrado_por"]
    assert api.get(f"/pagos/estado/{v.placa}").json()["estado"] == "VIGENTE"


@pytest.mark.parametrize("dias_fin,inicio", [
    (20, 21),    # vigente: empieza el día siguiente al vencimiento
    (0, 1),      # vence hoy: empieza mañana
    (-5, 0),     # vencida: empieza hoy
])
def test_inicio_del_nuevo_periodo_segun_el_estado(api_y_sesion, dias_fin, inicio):
    api, session = api_y_sesion
    v, hoy = vehiculo(session), hoy_bogota()
    crear_tarifa(session)
    periodo_antiguo(session, v, hoy - timedelta(days=40), hoy + timedelta(days=dias_fin))
    pago = pagar(api, v.placa).json()
    esperado = hoy + timedelta(days=inicio)
    assert pago["fecha_inicio"] == esperado.isoformat() and pago["fecha_fin"] == fin_de_periodo(esperado, 1).isoformat()


def test_vehiculo_vencido_que_paga_entra_de_inmediato(api_y_sesion):
    api, session = api_y_sesion
    v, hoy = vehiculo(session), hoy_bogota()
    crear_tarifa(session)
    periodo_antiguo(session, v, hoy - timedelta(days=40), hoy - timedelta(days=1))
    session.add(Celda(codigo=codigos_celda_libres(session, "CARRO")[0], tipo="CARRO"))
    session.flush()
    rechazo = api.post("/estancias/entrada", json={"placa": v.placa})
    assert rechazo.status_code == 409 and "mensualidad vigente" in rechazo.json()["detail"]
    assert pagar(api, v.placa).status_code == 201
    assert api.post("/estancias/entrada", json={"placa": v.placa}).status_code == 201


@pytest.mark.parametrize("cambios", [
    {"meses": 0}, {"meses": 7}, {"meses": 1.5}, {"meses": "2"}, {"meses": None},
    {"metodo": "CHEQUE"}, {"metodo": "efectivo"},
    {"metodo": "EFECTIVO", "referencia": "TRX-1234"},
    {"metodo": "TRANSFERENCIA"}, {"metodo": "TARJETA", "referencia": "   "},
    {"metodo": "TRANSFERENCIA", "referencia": "ABC"}, {"metodo": "TARJETA", "referencia": "x" * 31},
    {"metodo": "TRANSFERENCIA", "referencia": "con espacio"},
    {"monto_confirmado": 0}, {"monto_confirmado": 120000.0},
    # El responsable sale de la sesión: enviarlo se rechaza.
    {"registrado_por_cuenta_id": 1}, {"monto": 1000},
])
def test_registrar_pago_rechaza_datos_invalidos(api_y_sesion, cambios):
    api, session = api_y_sesion
    v = vehiculo(session)
    crear_tarifa(session)
    cuerpo = {"placa": v.placa, "meses": 1, "metodo": "EFECTIVO", "monto_confirmado": 120000, **cambios}
    respuesta = api.post("/pagos", json=cuerpo)
    assert respuesta.status_code == 422
    assert session.query(Mensualidad).filter_by(vehiculo_id=v.id).count() == 0


@pytest.mark.parametrize("metodo,referencia", [
    ("TRANSFERENCIA", "A1B2"), ("TARJETA", "x" * 30), ("EFECTIVO", ""), ("EFECTIVO", None),
])
def test_referencia_valida_en_sus_limites(api_y_sesion, metodo, referencia):
    api, session = api_y_sesion
    v = vehiculo(session)
    crear_tarifa(session)
    respuesta = pagar(api, v.placa, 1, metodo, referencia)
    assert respuesta.status_code == 201, respuesta.json()
    assert respuesta.json()["referencia"] == (referencia or None)


@pytest.mark.parametrize("meses", [1, 6])
def test_meses_validos_en_el_limite(api_y_sesion, meses):
    api, session = api_y_sesion
    v = vehiculo(session, "MOTO")
    crear_tarifa(session, "MOTO", 60000)
    pago = pagar(api, v.placa, meses).json()
    assert pago["meses"] == meses and pago["monto"] == 60000 * meses


def test_si_la_tarifa_cambio_despues_del_resumen_no_registra(api_y_sesion):
    api, session = api_y_sesion
    v = vehiculo(session)
    crear_tarifa(session, "AUTOMOVIL", 120000)
    monto_visto = api.get(f"/pagos/cotizacion?placa={v.placa}&meses=1").json()["monto"]
    crear_tarifa(session, "AUTOMOVIL", 130000)     # el Administrador cambia la tarifa entre resumen y confirmación
    respuesta = api.post("/pagos", json={"placa": v.placa, "meses": 1, "metodo": "EFECTIVO",
                                         "monto_confirmado": monto_visto})
    assert respuesta.status_code == 409 and "$ 130.000" in respuesta.json()["detail"]
    assert session.query(Mensualidad).filter_by(vehiculo_id=v.id).count() == 0
    assert pagar(api, v.placa).json()["valor_mensual"] == 130000


def test_monto_confirmado_distinto_sin_cambio_de_tarifa_no_registra(api_y_sesion):
    # PA-09, paso 1: el monto lo calcula el servidor; uno distinto se rechaza aunque la tarifa no cambie.
    api, session = api_y_sesion
    v = vehiculo(session)
    crear_tarifa(session, "AUTOMOVIL", 120000)
    respuesta = api.post("/pagos", json={"placa": v.placa, "meses": 1, "metodo": "EFECTIVO", "monto_confirmado": 1000})
    assert respuesta.status_code == 409
    assert respuesta.json() == {"detail": "El monto no coincide con el calculado: el monto vigente es $ 120.000. "
                                          "Revisa el nuevo resumen y confirma otra vez."}
    assert session.query(Mensualidad).filter_by(vehiculo_id=v.id).count() == 0


def test_sin_tarifa_definida_no_registra(api_y_sesion):
    api, session = api_y_sesion
    v = vehiculo(session, "CAMIONETA")
    assert api.get(f"/pagos/estado/{v.placa}").json()["tarifa"] is None
    respuesta = api.get(f"/pagos/cotizacion?placa={v.placa}&meses=1")
    assert respuesta.status_code == 409 and "No hay tarifa definida para CAMIONETA" in respuesta.json()["detail"]
    respuesta = api.post("/pagos", json={"placa": v.placa, "meses": 1, "metodo": "EFECTIVO", "monto_confirmado": 1000})
    assert respuesta.status_code == 409


def fin_antiguo_para(fin_buscado: date, hoy: date) -> date:
    """Fin de un periodo antiguo tal que un pago de 1 mes termine exactamente en fin_buscado."""
    for dias in range(300, 400):
        fin = hoy + timedelta(days=dias)
        if fin_de_periodo(fin + timedelta(days=1), 1) == fin_buscado:
            return fin
    raise AssertionError("No se encontró un fin adecuado")


def test_tope_de_pago_por_adelantado_en_el_limite(api_y_sesion):
    api, session = api_y_sesion
    hoy = hoy_bogota()
    tope = tope_de_adelanto(hoy)
    crear_tarifa(session)
    # Válido en el límite: el fin queda exactamente en hoy + 12 meses.
    limite = vehiculo(session)
    periodo_antiguo(session, limite, hoy - timedelta(days=30), fin_antiguo_para(tope, hoy))
    assert pagar(api, limite.placa).json()["fecha_fin"] == tope.isoformat()
    # Inválido en el límite: el fin quedaría un día después.
    pasado = vehiculo(session)
    periodo_antiguo(session, pasado, hoy - timedelta(days=30), fin_antiguo_para(tope + timedelta(days=1), hoy))
    respuesta = api.get(f"/pagos/cotizacion?placa={pasado.placa}&meses=1")
    assert respuesta.status_code == 409 and "12 meses" in respuesta.json()["detail"]
    respuesta = api.post("/pagos", json={"placa": pasado.placa, "meses": 1, "metodo": "EFECTIVO",
                                         "monto_confirmado": 120000})
    assert respuesta.status_code == 409 and "12 meses" in respuesta.json()["detail"]


def test_dos_pagos_de_6_meses_llegan_al_tope_y_el_tercero_se_rechaza(api_y_sesion):
    api, session = api_y_sesion
    v, hoy = vehiculo(session), hoy_bogota()
    crear_tarifa(session)
    primero = pagar(api, v.placa, 6).json()
    segundo = pagar(api, v.placa, 6).json()
    assert segundo["fecha_inicio"] == (date.fromisoformat(primero["fecha_fin"]) + timedelta(days=1)).isoformat()
    assert date.fromisoformat(segundo["fecha_fin"]) <= tope_de_adelanto(hoy)
    assert api.get(f"/pagos/cotizacion?placa={v.placa}&meses=1").status_code == 409


def test_operador_registra_pagos_y_sin_sesion_no(api_y_sesion):
    api, session = api_y_sesion
    v = vehiculo(session)
    crear_tarifa(session)
    autenticar(api, session, rol="OPERADOR")
    assert pagar(api, v.placa).status_code == 201
    for metodo, ruta in (("get", f"/pagos/estado/{v.placa}"), ("get", "/pagos"), ("post", "/pagos")):
        assert getattr(api, metodo)(ruta, headers={"Authorization": ""}).status_code == 401


# --- HU-31 Consultar pagos y comprobante ---

def test_listado_con_filtros(api_y_sesion):
    api, session = api_y_sesion
    hoy = hoy_bogota()
    a, b = vehiculo(session), vehiculo(session, "MOTO")
    crear_tarifa(session)
    crear_tarifa(session, "MOTO", 60000)
    pa = pagar(api, a.placa, 2, "TARJETA", "VOUCHER-77").json()
    pb = pagar(api, b.placa, 1).json()
    filas = api.get(f"/pagos?placa={a.placa[:3].lower()}-{a.placa[3:]}").json()
    assert filas["total"] == 1 and filas["items"][0]["comprobante"] == pa["comprobante"]
    fila = filas["items"][0]
    assert set(fila) == {"id", "comprobante", "fecha", "placa", "cliente_nombre", "fecha_inicio", "fecha_fin",
                         "meses", "monto", "metodo", "estado", "registrado_por"}
    assert [p["comprobante"] for p in api.get("/pagos?metodo=TARJETA&limit=100").json()["items"]
            if p["placa"] in {a.placa, b.placa}] == [pa["comprobante"]]
    hoy_txt = hoy.isoformat()
    del_dia = {p["comprobante"] for p in api.get(f"/pagos?desde={hoy_txt}&hasta={hoy_txt}&limit=100").json()["items"]}
    assert {pa["comprobante"], pb["comprobante"]} <= del_dia
    ayer = (hoy - timedelta(days=1)).isoformat()
    assert api.get(f"/pagos?placa={a.placa}&desde={ayer}&hasta={ayer}").json() == {
        "items": [], "total": 0, "offset": 0, "limit": 20}
    assert api.get(f"/pagos?placa={a.placa}&estado=ANULADO").json()["total"] == 0
    respuesta = api.get(f"/pagos?desde={hoy_txt}&hasta={ayer}")
    assert respuesta.status_code == 422 and "posterior" in respuesta.json()["detail"]
    assert api.get("/pagos?metodo=CHEQUE").status_code == 422
    assert api.get("/pagos?estado=BORRADO").status_code == 422


def test_detalle_del_pago_es_el_comprobante(api_y_sesion):
    api, session = api_y_sesion
    v = vehiculo(session)
    crear_tarifa(session)
    pago = pagar(api, v.placa).json()
    detalle = api.get(f"/pagos/{pago['id']}").json()
    assert detalle == pago
    assert detalle["cliente_documento"] and detalle["cliente_tipo_documento"] == "CC"
    assert detalle["anulado_en"] is None and detalle["anulado_por"] is None and detalle["motivo_anulacion"] is None
    assert api.get("/pagos/9223372036854775807").status_code == 404
    assert api.get("/pagos/0").status_code == 422


# --- HU-32 Anular pago ---

def test_anular_el_ultimo_pago_deja_la_traza_y_no_deja_entrar(api_y_sesion):
    api, session = api_y_sesion
    v = vehiculo(session)
    crear_tarifa(session)
    session.add(Celda(codigo=codigos_celda_libres(session, "CARRO")[0], tipo="CARRO"))
    session.flush()
    pago = pagar(api, v.placa).json()
    anulado = api.post(f"/pagos/{pago['id']}/anular", json={"motivo": "  Error al digitar la placa  "})
    assert anulado.status_code == 200, anulado.json()
    a = anulado.json()
    assert a["estado"] == "ANULADO" and a["motivo_anulacion"] == "Error al digitar la placa"
    assert a["anulado_por"] and a["anulado_en"] and a["anulable"] is False
    # Nunca se elimina: sigue en el listado, como ANULADO.
    assert api.get(f"/pagos?placa={v.placa}&estado=ANULADO").json()["total"] == 1
    # Su periodo deja de habilitar la entrada.
    assert api.get(f"/pagos/estado/{v.placa}").json()["estado"] == "SIN_MENSUALIDAD"
    assert api.post("/estancias/entrada", json={"placa": v.placa}).status_code == 409
    otra = api.post(f"/pagos/{pago['id']}/anular", json={"motivo": "Segundo intento de anular"})
    assert otra.status_code == 409 and "ya está anulado" in otra.json()["detail"]


def test_solo_se_anula_el_ultimo_periodo(api_y_sesion):
    api, session = api_y_sesion
    v = vehiculo(session)
    crear_tarifa(session)
    primero, segundo = pagar(api, v.placa).json(), pagar(api, v.placa).json()
    assert api.get(f"/pagos/{primero['id']}").json()["anulable"] is False
    assert api.get(f"/pagos/{segundo['id']}").json()["anulable"] is True
    respuesta = api.post(f"/pagos/{primero['id']}/anular", json={"motivo": "Error al digitar la placa"})
    assert respuesta.status_code == 409 and "último periodo" in respuesta.json()["detail"]
    # Anulado el último, el anterior pasa a ser el último y el siguiente pago empieza tras él.
    assert api.post(f"/pagos/{segundo['id']}/anular", json={"motivo": "Cobro duplicado por error"}).status_code == 200
    assert api.get(f"/pagos/{primero['id']}").json()["anulable"] is True
    nuevo = pagar(api, v.placa).json()
    assert nuevo["fecha_inicio"] == (date.fromisoformat(primero["fecha_fin"]) + timedelta(days=1)).isoformat()


@pytest.mark.parametrize("motivo", ["a" * 9, "a" * 201, "          ", ""])
def test_motivo_de_anulacion_invalido(api_y_sesion, motivo):
    api, session = api_y_sesion
    v = vehiculo(session)
    crear_tarifa(session)
    pago = pagar(api, v.placa).json()
    assert api.post(f"/pagos/{pago['id']}/anular", json={"motivo": motivo}).status_code == 422
    assert api.get(f"/pagos/{pago['id']}").json()["estado"] == "VALIDO"


@pytest.mark.parametrize("motivo", ["a" * 10, "a" * 200])
def test_motivo_de_anulacion_en_el_limite(api_y_sesion, motivo):
    api, session = api_y_sesion
    v = vehiculo(session)
    crear_tarifa(session)
    pago = pagar(api, v.placa).json()
    assert api.post(f"/pagos/{pago['id']}/anular", json={"motivo": motivo}).json()["motivo_anulacion"] == motivo


def test_operador_no_anula(api_y_sesion):
    api, session = api_y_sesion
    v = vehiculo(session)
    crear_tarifa(session)
    pago = pagar(api, v.placa).json()
    autenticar(api, session, rol="OPERADOR")
    respuesta = api.post(f"/pagos/{pago['id']}/anular", json={"motivo": "Error al digitar la placa"})
    assert respuesta.status_code == 403
    assert respuesta.json() == {"detail": SIN_PERMISO}
    assert api.get(f"/pagos/{pago['id']}").json()["estado"] == "VALIDO"


def test_anular_pago_inexistente(api_y_sesion):
    api, _ = api_y_sesion
    assert api.post("/pagos/9223372036854775807/anular", json={"motivo": "Error al digitar"}).status_code == 404
