"""Pruebas unitarias y de valores límite de las reglas de negocio (sin base de datos)."""

from datetime import date

import pytest

from app.domain.reglas import (
    fin_de_mensualidad, mensualidad_vigente, normalizar_placa, sumar_meses, validar_modelo, validar_placa,
)

HOY = date(2026, 10, 23)


@pytest.mark.parametrize("entrada,esperada", [
    ("abc123", "ABC123"), (" abc 123 ", "ABC123"), ("ABC-123", "ABC123"),
    ("abc - 12d", "ABC12D"), ("\tkl m-45d\n", "KLM45D"),
])
def test_normaliza_placa(entrada, esperada):
    assert normalizar_placa(entrada) == esperada


@pytest.mark.parametrize("entrada", ["", "   ", "--", " - "])
def test_placa_vacia_tras_normalizar(entrada):
    with pytest.raises(ValueError):
        normalizar_placa(entrada)


@pytest.mark.parametrize("placa,tipo", [
    ("ABC123", "AUTOMOVIL"), ("abc-123", "CAMIONETA"), ("ABC12D", "MOTO"), ("xyz 98 a", "MOTO"),
])
def test_placas_validas(placa, tipo):
    assert validar_placa(placa, tipo) == normalizar_placa(placa)


@pytest.mark.parametrize("placa,tipo", [
    ("AB123", "AUTOMOVIL"),     # faltan letras
    ("ABCD123", "AUTOMOVIL"),   # sobran letras
    ("ABC1234", "AUTOMOVIL"),   # sobran números
    ("ABC12D", "AUTOMOVIL"),    # formato de moto en un carro
    ("ABC123", "MOTO"),         # formato de carro en una moto
    ("ABC1DD", "MOTO"),
    ("ÑBC123", "AUTOMOVIL"),    # solo letras A-Z
    ("123ABC", "CAMIONETA"),
])
def test_placas_invalidas(placa, tipo):
    with pytest.raises(ValueError):
        validar_placa(placa, tipo)


@pytest.mark.parametrize("anio", [1900, 1901, 2026, 2027])
def test_modelo_en_limites(anio):
    assert validar_modelo(anio, HOY) == anio


@pytest.mark.parametrize("anio", [1899, 2028, 0])
def test_modelo_fuera_de_limites(anio):
    with pytest.raises(ValueError):
        validar_modelo(anio, HOY)


def test_modelo_maximo_depende_del_anio_actual():
    assert validar_modelo(2028, date(2027, 1, 1)) == 2028


@pytest.mark.parametrize("inicio,fin", [
    (date(2026, 10, 20), date(2026, 11, 20)),   # fecha a fecha
    (date(2026, 12, 15), date(2027, 1, 15)),    # cambio de año
    (date(2027, 1, 31), date(2027, 2, 28)),     # febrero no tiene 31
    (date(2028, 1, 31), date(2028, 2, 29)),     # año bisiesto
    (date(2026, 3, 31), date(2026, 4, 30)),     # abril tiene 30 días
    (date(2026, 2, 28), date(2026, 3, 28)),     # no salta a fin de mes
])
def test_fin_de_mensualidad_fecha_a_fecha(inicio, fin):
    assert fin_de_mensualidad(inicio) == fin


def test_restar_meses():
    assert sumar_meses(date(2026, 3, 31), -1) == date(2026, 2, 28)
    assert sumar_meses(date(2026, 1, 15), -1) == date(2025, 12, 15)


@pytest.mark.parametrize("hoy,vigente", [
    (date(2026, 10, 19), False),  # un día antes del inicio
    (date(2026, 10, 20), True),   # día de inicio
    (date(2026, 11, 5), True),
    (date(2026, 11, 20), True),   # día de vencimiento: todavía puede entrar
    (date(2026, 11, 21), False),  # un día después
])
def test_vigencia_en_limites(hoy, vigente):
    assert mensualidad_vigente(date(2026, 10, 20), date(2026, 11, 20), hoy) is vigente
