"""Reglas del parqueadero. Funciones puras para probarlas sin base de datos."""

import calendar
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

ZONA_BOGOTA = ZoneInfo("America/Bogota")
MODELO_MINIMO = 1900

# Carro (automóvil o camioneta): 3 letras + 3 números. Moto: 3 letras + 2 números + 1 letra.
PLACA_CARRO = re.compile(r"[A-Z]{3}[0-9]{3}")
PLACA_MOTO = re.compile(r"[A-Z]{3}[0-9]{2}[A-Z]")


def required_text(value: str, attribute: str) -> str:
    """Texto obligatorio: rechaza lo que no es texto o está vacío y quita los espacios exteriores.

    Vive en el dominio porque lo usan los modelos, los schemas y los servicios.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{attribute} debe ser texto no vacío.")
    return value.strip()


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


# --- Celdas y estancias (Fase 2) ---

TOTAL_CELDAS = {"CARRO": 70, "MOTO": 10}
# Automóvil y camioneta usan celda de carro; no se reciben camiones.
TIPO_CELDA_POR_VEHICULO = {"MOTO": "MOTO", "AUTOMOVIL": "CARRO", "CAMIONETA": "CARRO"}


def tipo_celda_para(tipo_vehiculo: str) -> str:
    try:
        return TIPO_CELDA_POR_VEHICULO[tipo_vehiculo]
    except KeyError:
        raise ValueError(f"Tipo de vehículo no admitido: {tipo_vehiculo}.") from None


def orden_de_asignacion(disponible_desde: datetime | None, codigo: str) -> tuple:
    """Clave para elegir celda libre: primero las nunca usadas (None), luego la que lleva
    más tiempo libre y, si empatan, el código. Así el uso se reparte entre todas.

    El servicio usa este mismo orden en SQL: ORDER BY disponible_desde NULLS FIRST, codigo.
    """
    return (disponible_desde is not None, disponible_desde or datetime.min, codigo)


def permanencia_segundos(entrada: datetime, salida: datetime) -> int:
    return max(0, int((salida - entrada).total_seconds()))


def formatear_permanencia(segundos: int) -> str:
    """3 h 05 min; 2 d 4 h 10 min; menos de un minuto: 0 min."""
    minutos_totales = segundos // 60
    dias, resto = divmod(minutos_totales, 24 * 60)
    horas, minutos = divmod(resto, 60)
    if dias:
        return f"{dias} d {horas} h {minutos:02d} min"
    if horas:
        return f"{horas} h {minutos:02d} min"
    return f"{minutos} min"


# --- Corrección de celda y novedades (Fase 3) ---

MOTIVO_MAXIMO = 200        # "texto corto" para la corrección de celda
DESCRIPCION_MAXIMA = 500
TIPOS_NOVEDAD = {
    "RAYON": "Rayón",
    "GOLPE": "Golpe",
    "OBJETO_OLVIDADO": "Objeto olvidado",
    "OTRO": "Otro",
}


def validar_celda_compatible(tipo_vehiculo: str, tipo_celda: str, codigo: str) -> None:
    """Una moto solo va en celda MOTO; automóvil y camioneta, en celda CARRO."""
    necesaria = tipo_celda_para(tipo_vehiculo)
    if tipo_celda != necesaria:
        raise ValueError(
            f"La celda {codigo} es de {tipo_celda.lower()}; el vehículo necesita celda de {necesaria.lower()}."
        )


def validar_texto_corto(texto: str, maximo: int, campo: str) -> str:
    texto = " ".join(texto.split())
    if not texto:
        raise ValueError(f"El {campo} es obligatorio.")
    if len(texto) > maximo:
        raise ValueError(f"El {campo} admite máximo {maximo} caracteres.")
    return texto


# --- Historial (Fase 4) ---

def rango_bogota(desde: date | None, hasta: date | None) -> tuple[datetime | None, datetime | None]:
    """Convierte días de Bogotá (ambos incluidos) en instantes [inicio, fin) para filtrar entradas.

    Ejemplo: del 23 al 23 de octubre = desde 23-oct 00:00 hasta 24-oct 00:00 (hora de Bogotá).
    """
    if desde is not None and hasta is not None and desde > hasta:
        raise ValueError("La fecha 'desde' no puede ser posterior a 'hasta'.")
    inicio = datetime.combine(desde, datetime.min.time(), ZONA_BOGOTA) if desde else None
    fin = datetime.combine(hasta + timedelta(days=1), datetime.min.time(), ZONA_BOGOTA) if hasta else None
    return inicio, fin


# --- Iteración 2: cuentas de usuario y gestión de celdas ---
# Los mismos límites se repiten en los CHECK de la base (migraciones 0006 y 0007) y en Angular.

ROLES = ("ADMINISTRADOR", "OPERADOR")
USUARIO_MINIMO, USUARIO_MAXIMO = 4, 30
NOMBRE_MINIMO, NOMBRE_MAXIMO = 3, 80
CONTRASENA_MINIMA, CONTRASENA_MAXIMA = 8, 64
CONTRASENA_MAXIMA_BYTES = 72        # bcrypt solo procesa 72 bytes
UBICACION_MAXIMA = 60
PREFIJO_CELDA = {"CARRO": "C", "MOTO": "M"}

PATRON_USUARIO = re.compile(rf"[a-z0-9._]{{{USUARIO_MINIMO},{USUARIO_MAXIMO}}}")
PATRON_CODIGO_CELDA = re.compile(r"[CM](0[1-9]|[1-9][0-9])")


def normalizar_usuario(usuario: str) -> str:
    """Quita los espacios exteriores y pasa a minúsculas: ' Marta.Usuga ' -> 'marta.usuga'."""
    return usuario.strip().lower()


def validar_nombre_usuario(usuario: str) -> str:
    """Normaliza y comprueba: 4 a 30 caracteres entre minúsculas, dígitos, punto y guion bajo."""
    usuario = normalizar_usuario(usuario)
    if not PATRON_USUARIO.fullmatch(usuario):
        raise ValueError(
            f"El nombre de usuario debe tener de {USUARIO_MINIMO} a {USUARIO_MAXIMO} caracteres: "
            "letras minúsculas, dígitos, punto o guion bajo."
        )
    return usuario


def validar_nombre_completo(nombre: str) -> str:
    """Quita los espacios exteriores y exige de 3 a 80 caracteres."""
    nombre = nombre.strip()
    if not NOMBRE_MINIMO <= len(nombre) <= NOMBRE_MAXIMO:
        raise ValueError(f"El nombre completo debe tener de {NOMBRE_MINIMO} a {NOMBRE_MAXIMO} caracteres.")
    return nombre


def validar_contrasena(contrasena: str) -> str:
    """De 8 a 64 caracteres, con al menos una letra y un número. No se recorta: los espacios cuentan."""
    if not CONTRASENA_MINIMA <= len(contrasena) <= CONTRASENA_MAXIMA:
        raise ValueError(f"La contraseña debe tener de {CONTRASENA_MINIMA} a {CONTRASENA_MAXIMA} caracteres.")
    if not any(c.isalpha() for c in contrasena) or not any(c in "0123456789" for c in contrasena):
        raise ValueError("La contraseña debe tener al menos una letra y un número.")
    if len(contrasena.encode("utf-8")) > CONTRASENA_MAXIMA_BYTES:
        raise ValueError("La contraseña es demasiado larga: usa menos caracteres especiales.")
    return contrasena


def normalizar_codigo_celda(codigo: str) -> str:
    """Quita los espacios exteriores y pasa a mayúsculas: ' c05 ' -> 'C05'."""
    return codigo.strip().upper()


def validar_codigo_celda(codigo: str, tipo: str) -> str:
    """C (carro) o M (moto) seguido de dos dígitos del 01 al 99; el prefijo debe coincidir con el tipo."""
    codigo = normalizar_codigo_celda(codigo)
    if not PATRON_CODIGO_CELDA.fullmatch(codigo):
        raise ValueError("El código debe ser C o M seguido de dos dígitos del 01 al 99 (ej. C05).")
    prefijo = PREFIJO_CELDA.get(tipo)
    if prefijo is None:
        raise ValueError("El tipo de celda debe ser CARRO o MOTO.")
    if codigo[0] != prefijo:
        raise ValueError(f"Una celda de tipo {tipo} debe tener un código que empiece por {prefijo}.")
    return codigo


def normalizar_ubicacion(ubicacion: str | None) -> str | None:
    """Opcional: quita los espacios exteriores, vacía se guarda como NULL, máximo 60 caracteres."""
    if ubicacion is None or not ubicacion.strip():
        return None
    ubicacion = ubicacion.strip()
    if len(ubicacion) > UBICACION_MAXIMA:
        raise ValueError(f"La ubicación admite máximo {UBICACION_MAXIMA} caracteres.")
    return ubicacion
