"""Iteración 3: reglas de pagos, tarifas y clientes con los valores límite del documento (sin base de datos)."""

from datetime import date, timedelta

import pytest

from app.domain.pagos import (
    PAGADA_A_FUTURO, SIN_MENSUALIDAD, VENCIDA, VIGENTE, Periodo, calcular_monto, estado_mensualidad,
    fin_de_periodo, formatear_pesos, inicio_de_periodo, normalizar_correo, normalizar_documento, normalizar_referencia,
    tope_de_adelanto, validar_meses, validar_metodo, validar_motivo_anulacion, validar_telefono,
    validar_tipo_documento, validar_tipo_vehiculo, validar_tope_de_adelanto, validar_valor_tarifa,
)
from app.domain.reglas import validar_nombre_completo

HOY = date(2026, 11, 20)


# --- Fin del periodo (D13 y tabla de reglas) ---

@pytest.mark.parametrize("inicio,meses,fin", [
    (date(2026, 11, 20), 1, date(2026, 12, 19)),   # ejemplo del documento
    (date(2027, 1, 31), 1, date(2027, 2, 28)),     # ejemplo del documento: 31-feb no existe
    (date(2026, 12, 15), 2, date(2027, 2, 14)),    # ejemplo del documento, con cambio de año
    (date(2028, 1, 31), 1, date(2028, 2, 29)),     # año bisiesto
    (date(2027, 1, 29), 1, date(2027, 2, 28)),     # 29-feb no existe en 2027
    (date(2027, 1, 30), 1, date(2027, 2, 28)),
    (date(2028, 1, 29), 1, date(2028, 2, 28)),     # en 2028 el 29-feb sí existe: termina el 28
    (date(2026, 3, 31), 1, date(2026, 4, 30)),     # abril tiene 30 días
    (date(2026, 8, 31), 6, date(2027, 2, 28)),     # 6 meses que caen en febrero
    (date(2027, 2, 28), 1, date(2027, 3, 27)),     # no salta a fin de mes
    (date(2026, 3, 1), 1, date(2026, 3, 31)),      # mes completo
    (date(2026, 11, 15), 2, date(2027, 1, 14)),
    (date(2026, 12, 31), 1, date(2027, 1, 30)),
    (date(2026, 1, 1), 6, date(2026, 6, 30)),
    (date(2026, 11, 20), 6, date(2027, 5, 19)),
])
def test_fin_de_periodo(inicio, meses, fin):
    assert fin_de_periodo(inicio, meses) == fin


@pytest.mark.parametrize("inicio", [date(2026, 11, 20), date(2027, 1, 31), date(2026, 1, 1), date(2028, 1, 30)])
def test_periodos_encadenados_sin_huecos_ni_superposicion(inicio):
    # 12 pagos seguidos de 1 mes: cada uno empieza el día siguiente al fin del anterior.
    periodo_inicio = inicio
    for _ in range(12):
        fin = fin_de_periodo(periodo_inicio, 1)
        assert fin >= periodo_inicio
        siguiente = inicio_de_periodo(fin, periodo_inicio)
        assert siguiente == fin + timedelta(days=1)
        periodo_inicio = siguiente


def test_un_pago_de_n_meses_termina_igual_que_n_pagos_de_1_mes_desde_el_dia_1():
    inicio, fin = date(2026, 1, 1), None
    for _ in range(6):
        fin = fin_de_periodo(inicio, 1)
        inicio = fin + timedelta(days=1)
    assert fin == fin_de_periodo(date(2026, 1, 1), 6) == date(2026, 6, 30)


# --- Inicio del periodo (D13) ---

@pytest.mark.parametrize("ultimo_fin,inicio", [
    (None, HOY),                                    # sin mensualidad: empieza hoy
    (HOY - timedelta(days=1), HOY),                 # venció ayer: empieza hoy
    (HOY - timedelta(days=40), HOY),                # vencida hace tiempo
    (HOY, HOY + timedelta(days=1)),                 # vence hoy: empieza mañana
    (HOY + timedelta(days=10), HOY + timedelta(days=11)),   # vigente: día siguiente al fin
    (HOY + timedelta(days=60), HOY + timedelta(days=61)),   # pagada a futuro: después del último fin
])
def test_inicio_de_periodo(ultimo_fin, inicio):
    assert inicio_de_periodo(ultimo_fin, HOY) == inicio


# --- Tope de pago por adelantado: fin <= hoy + 12 meses ---

def test_tope_de_adelanto_en_el_limite():
    tope = tope_de_adelanto(HOY)
    assert tope == date(2027, 11, 20)
    assert validar_tope_de_adelanto(tope, HOY) == tope              # exactamente hoy + 12 meses
    with pytest.raises(ValueError, match="12 meses"):
        validar_tope_de_adelanto(tope + timedelta(days=1), HOY)     # un día después


def test_tope_de_adelanto_en_29_de_febrero():
    assert tope_de_adelanto(date(2028, 2, 29)) == date(2029, 2, 28)


# --- Estado de la mensualidad (RF-35) ---

def p(desde: int, hasta: int) -> Periodo:
    return Periodo(HOY + timedelta(days=desde), HOY + timedelta(days=hasta))


def test_sin_mensualidad():
    estado = estado_mensualidad([], HOY)
    assert estado.estado == SIN_MENSUALIDAD and estado.actual is None and estado.ultimo_fin is None


def test_vigente_con_dias_restantes():
    estado = estado_mensualidad([p(-10, 20)], HOY)
    assert estado.estado == VIGENTE and estado.actual == p(-10, 20)
    assert estado.vence == HOY + timedelta(days=20) and estado.dias_restantes == 20 and estado.futuros == []


@pytest.mark.parametrize("fin,dias", [(0, 0), (1, 1)])
def test_dias_restantes_en_el_limite(fin, dias):
    # El día del fin todavía está vigente: "vence hoy" = 0 días.
    estado = estado_mensualidad([p(-30, fin)], HOY)
    assert estado.estado == VIGENTE and estado.dias_restantes == dias


def test_vigente_con_periodos_pagados_hacia_adelante_cuenta_hasta_el_ultimo_encadenado():
    estado = estado_mensualidad([p(-10, 5), p(6, 36), p(37, 67)], HOY)
    assert estado.estado == VIGENTE and estado.actual == p(-10, 5)
    assert estado.futuros == [p(6, 36), p(37, 67)]
    assert estado.vence == HOY + timedelta(days=67) and estado.dias_restantes == 67
    assert estado.ultimo_fin == HOY + timedelta(days=67)


def test_un_hueco_corta_el_vencimiento():
    estado = estado_mensualidad([p(-10, 5), p(8, 30)], HOY)
    assert estado.vence == HOY + timedelta(days=5) and estado.ultimo_fin == HOY + timedelta(days=30)


def test_periodos_antiguos_que_se_tocan_un_dia():
    # Semilla JKL321 (EA1): el segundo periodo empieza el mismo día en que termina el primero.
    estado = estado_mensualidad([p(-40, -9), p(-9, 21)], HOY)
    assert estado.estado == VIGENTE and estado.actual == p(-9, 21) and estado.vence == HOY + timedelta(days=21)


def test_vencida():
    estado = estado_mensualidad([p(-70, -40), p(-39, -5)], HOY)
    assert estado.estado == VENCIDA and estado.vence == HOY - timedelta(days=5) and estado.dias_restantes is None


def test_vence_ayer_ya_esta_vencida():
    assert estado_mensualidad([p(-30, -1)], HOY).estado == VENCIDA


def test_pagada_a_futuro():
    estado = estado_mensualidad([p(1, 31)], HOY)
    assert estado.estado == PAGADA_A_FUTURO and estado.actual is None and estado.futuros == [p(1, 31)]
    assert estado.vence == HOY + timedelta(days=31) and estado.ultimo_fin == HOY + timedelta(days=31)


def test_vencida_con_periodo_futuro_es_pagada_a_futuro():
    assert estado_mensualidad([p(-60, -30), p(3, 33)], HOY).estado == PAGADA_A_FUTURO


# --- Monto (D11) y validaciones con valores límite ---

@pytest.mark.parametrize("meses", [1, 6])
def test_meses_validos_en_el_limite(meses):
    assert validar_meses(meses) == meses


@pytest.mark.parametrize("meses", [0, 7, 1.5, -1, True, "3", None])
def test_meses_invalidos(meses):
    with pytest.raises(ValueError, match="de 1 a 6"):
        validar_meses(meses)


@pytest.mark.parametrize("valor", [1_000, 2_000_000])
def test_tarifa_valida_en_el_limite(valor):
    assert validar_valor_tarifa(valor) == valor


@pytest.mark.parametrize("valor", [999, 2_000_001, 1000.5, 120000.0, 0, -1000, True, "120000", None])
def test_tarifa_invalida(valor):
    with pytest.raises(ValueError, match="sin decimales"):
        validar_valor_tarifa(valor)


def test_monto_es_tarifa_por_meses():
    assert calcular_monto(1_000, 1) == 1_000
    assert calcular_monto(2_000_000, 6) == 12_000_000
    assert calcular_monto(120_000, 3) == 360_000
    with pytest.raises(ValueError):
        calcular_monto(120_000, 7)


@pytest.mark.parametrize("tipo", ["MOTO", "AUTOMOVIL", "CAMIONETA"])
def test_tipos_de_vehiculo_de_las_tarifas(tipo):
    assert validar_tipo_vehiculo(tipo) == tipo


@pytest.mark.parametrize("tipo", ["CARRO", "CAMION", "moto", ""])
def test_tipo_de_vehiculo_invalido(tipo):
    with pytest.raises(ValueError):
        validar_tipo_vehiculo(tipo)


@pytest.mark.parametrize("metodo", ["EFECTIVO", "TRANSFERENCIA", "TARJETA"])
def test_metodos_validos(metodo):
    assert validar_metodo(metodo) == metodo


@pytest.mark.parametrize("metodo", ["CHEQUE", "efectivo", "", "BITCOIN"])
def test_metodo_invalido(metodo):
    with pytest.raises(ValueError, match="EFECTIVO, TRANSFERENCIA o TARJETA"):
        validar_metodo(metodo)


@pytest.mark.parametrize("metodo", ["TRANSFERENCIA", "TARJETA"])
@pytest.mark.parametrize("referencia", ["A1B2", "x" * 30, "TRX-2026-0001", " ab-12 "])
def test_referencia_valida(metodo, referencia):
    assert normalizar_referencia(metodo, referencia) == referencia.strip()


@pytest.mark.parametrize("referencia", ["ABC", "x" * 31, "con espacio", "abc_123", "ñandú1"])
def test_referencia_con_formato_invalido(referencia):
    with pytest.raises(ValueError, match="de 4 a 30"):
        normalizar_referencia("TRANSFERENCIA", referencia)


@pytest.mark.parametrize("referencia", [None, "", "   "])
def test_referencia_vacia_en_transferencia_o_tarjeta(referencia):
    for metodo in ("TRANSFERENCIA", "TARJETA"):
        with pytest.raises(ValueError, match="obligatoria"):
            normalizar_referencia(metodo, referencia)


@pytest.mark.parametrize("referencia", [None, "", "  "])
def test_efectivo_sin_referencia(referencia):
    assert normalizar_referencia("EFECTIVO", referencia) is None


def test_efectivo_con_referencia():
    with pytest.raises(ValueError, match="efectivo no lleva referencia"):
        normalizar_referencia("EFECTIVO", "TRX-1234")


@pytest.mark.parametrize("motivo", ["a" * 10, "a" * 200, "  " + "a" * 10 + "  ", "Error al digitar la placa"])
def test_motivo_de_anulacion_valido(motivo):
    assert validar_motivo_anulacion(motivo) == motivo.strip()


@pytest.mark.parametrize("motivo,mensaje", [
    ("a" * 9, "de 10 a 200"), ("a" * 201, "de 10 a 200"), ("   " + "a" * 9 + "   ", "de 10 a 200"),
    ("", "obligatorio"), ("          ", "obligatorio"), (None, "obligatorio"),
])
def test_motivo_de_anulacion_invalido(motivo, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        validar_motivo_anulacion(motivo)


# --- Cliente ---

@pytest.mark.parametrize("tipo", ["CC", "CE", "PA"])
def test_tipos_de_documento(tipo):
    assert validar_tipo_documento(tipo) == tipo


@pytest.mark.parametrize("tipo", ["TI", "NIT", "cc", ""])
def test_tipo_de_documento_invalido(tipo):
    with pytest.raises(ValueError, match="CC, CE o PA"):
        validar_tipo_documento(tipo)


@pytest.mark.parametrize("documento,normalizado", [
    ("12345", "12345"), ("1" * 15, "1" * 15), (" ab12345 ", "AB12345"), ("Pa1234567", "PA1234567"),
])
def test_documento_valido_en_el_limite(documento, normalizado):
    assert normalizar_documento(documento) == normalizado


@pytest.mark.parametrize("documento", ["1234", "1" * 16, "1.234.567", "123 456", "12345-6", "", "     "])
def test_documento_invalido(documento):
    with pytest.raises(ValueError, match="de 5 a 15"):
        normalizar_documento(documento)


@pytest.mark.parametrize("nombre", ["Ana", "a" * 80, "  Ana  "])
def test_nombre_del_cliente_valido(nombre):
    assert validar_nombre_completo(nombre) == nombre.strip()


@pytest.mark.parametrize("nombre", ["Al", "a" * 81, "     ", ""])
def test_nombre_del_cliente_invalido(nombre):
    with pytest.raises(ValueError, match="de 3 a 80"):
        validar_nombre_completo(nombre)


@pytest.mark.parametrize("telefono", ["3001112233", " 3001112233 "])
def test_telefono_valido(telefono):
    assert validar_telefono(telefono) == "3001112233"


@pytest.mark.parametrize("telefono", ["300111223", "30011122334", "300111223a", "300 111 2233", "", "+573001112"])
def test_telefono_invalido(telefono):
    with pytest.raises(ValueError, match="10 dígitos"):
        validar_telefono(telefono)


@pytest.mark.parametrize("correo,normalizado", [
    (None, None), ("", None), ("   ", None), ("ana@correo.com", "ana@correo.com"), (" ana@correo.com ", "ana@correo.com"),
])
def test_correo_opcional_valido(correo, normalizado):
    assert normalizar_correo(correo) == normalizado


@pytest.mark.parametrize("correo", ["ana@", "texto sin arroba", "ana@correo", "@correo.com", "ana@@correo.com"])
def test_correo_invalido(correo):
    with pytest.raises(ValueError, match="formato válido"):
        normalizar_correo(correo)


@pytest.mark.parametrize("valor,texto", [
    (0, "$ 0"), (1_000, "$ 1.000"), (120_000, "$ 120.000"), (2_000_000, "$ 2.000.000"), (12_000_000, "$ 12.000.000"),
])
def test_formato_de_pesos(valor, texto):
    # RNF-22: pesos enteros con el formato $ 120.000.
    assert formatear_pesos(valor) == texto
