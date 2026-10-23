"""Reglas del parqueadero. Funciones puras para probarlas sin base de datos."""

import calendar
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

ZONA_BOGOTA = ZoneInfo("America/Bogota")
MODELO_MINIMO = 1900

# Carro (automóvil o camioneta): 3 letras + 3 números. Moto: 3 letras + 2 números + 1 letra.
PLACA_CARRO = re.compile(r"[A-Z]{3}[0-9]{3}")
PLACA_MOTO = re.compile(r"[A-Z]{3}[0-9]{2}[A-Z]")


def hoy_bogota() -> date:
    """Fecha de hoy en Colombia, sin importar la zona horaria del servidor."""
    return datetime.now(ZONA_BOGOTA).date()


def normalizar_placa(placa: str) -> str:
    """Quita espacios y guiones y pasa a mayúsculas: ' abc-123 ' -> 'ABC123'."""
    normalizada = re.sub(r"[\s-]+", "", placa).upper()
    if not normalizada:
        raise ValueError("La placa no puede estar vacía.")
    return normalizada


def validar_placa(placa: str, tipo: str) -> str:
    """Comprueba el formato según el tipo de vehículo y devuelve la placa normalizada."""
    placa = normalizar_placa(placa)
    if tipo == "MOTO":
        if not PLACA_MOTO.fullmatch(placa):
            raise ValueError("La placa de moto debe tener 3 letras, 2 números y 1 letra (ej. ABC12D).")
    elif not PLACA_CARRO.fullmatch(placa):
        raise ValueError("La placa de carro debe tener 3 letras y 3 números (ej. ABC123).")
    return placa


def validar_modelo(anio: int, hoy: date) -> int:
    """El modelo (año) va de 1900 al año actual + 1."""
    maximo = hoy.year + 1
    if not MODELO_MINIMO <= anio <= maximo:
        raise ValueError(f"El modelo debe ser un año entre {MODELO_MINIMO} y {maximo}.")
    return anio


def sumar_meses(fecha: date, meses: int) -> date:
    """Suma meses calendario. Si el día no existe en el mes destino, usa el último día.

    Ejemplo: 31 de enero + 1 mes = 28 (o 29) de febrero.
    """
    indice = fecha.year * 12 + (fecha.month - 1) + meses
    anio, mes = divmod(indice, 12)
    mes += 1
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, min(fecha.day, ultimo_dia))


def fin_de_mensualidad(inicio: date) -> date:
    """La mensualidad va de fecha a fecha: pagó el 20 de octubre, vence el 20 de noviembre."""
    return sumar_meses(inicio, 1)


def mensualidad_vigente(inicio: date, fin: date, hoy: date) -> bool:
    """Vigente si inicio <= hoy <= fin (ambos días incluidos)."""
    return inicio <= hoy <= fin
