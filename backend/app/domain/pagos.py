"""Reglas de la Iteración 3 (pagos, tarifas y clientes). Funciones puras: se prueban sin base de datos.

Los mismos límites se repiten en los CHECK de la base (migraciones 0009 y 0010) y en Angular
(RNF-16: tres niveles con las mismas reglas).
"""

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.domain.reglas import sumar_meses

# --- Límites de la tabla de reglas (documento EA3, sección 3) ---

TIPOS_VEHICULO = ("MOTO", "AUTOMOVIL", "CAMIONETA")   # las tarifas van por tipo de vehículo (D12)
MESES_MINIMO, MESES_MAXIMO = 1, 6                      # meses por pago (D9)
MESES_ADELANTO_MAXIMO = 12                             # el fin no puede pasar de hoy + 12 meses
TARIFA_MINIMA, TARIFA_MAXIMA = 1_000, 2_000_000        # pesos enteros (RNF-22)
METODOS_PAGO = ("EFECTIVO", "TRANSFERENCIA", "TARJETA")
REFERENCIA_MINIMA, REFERENCIA_MAXIMA = 4, 30
MOTIVO_ANULACION_MINIMO, MOTIVO_ANULACION_MAXIMO = 10, 200
TIPOS_DOCUMENTO = ("CC", "CE", "PA")
DOCUMENTO_MINIMO, DOCUMENTO_MAXIMO = 5, 15

PATRON_REFERENCIA = re.compile(rf"[A-Za-z0-9-]{{{REFERENCIA_MINIMA},{REFERENCIA_MAXIMA}}}")
PATRON_DOCUMENTO = re.compile(rf"[A-Z0-9]{{{DOCUMENTO_MINIMO},{DOCUMENTO_MAXIMO}}}")
PATRON_TELEFONO = re.compile(r"[0-9]{10}")
# La misma expresión del CHECK ck_cliente_correo_formato (migración 0003).
PATRON_CORREO = re.compile(r"[^@\s]+@[^@\s]+[.][^@\s]+")

# Estados de la mensualidad de un vehículo (RF-35).
VIGENTE, VENCIDA, SIN_MENSUALIDAD, PAGADA_A_FUTURO = "VIGENTE", "VENCIDA", "SIN_MENSUALIDAD", "PAGADA_A_FUTURO"


# --- Fechas del periodo (D13) ---

def fin_de_periodo(inicio: date, meses: int) -> date:
    """Día anterior a la misma fecha N meses después. Si esa fecha no existe en el mes destino,
    se toma el primer día del mes siguiente, así que el fin es el último día del mes destino.

    Ejemplos: 20-nov + 1 mes -> 19-dic; 31-ene + 1 mes -> 28-feb (29 en año bisiesto);
    15-dic + 2 meses -> 14-feb. Encadenados no dejan huecos: 20-nov a 19-dic, luego 20-dic a 19-ene.
    Solo para los periodos pagados desde la Iteración 3; los anteriores usan fin_de_mensualidad.
    """
    indice = inicio.year * 12 + (inicio.month - 1) + meses
    anio, mes = divmod(indice, 12)
    mes += 1
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    if inicio.day > ultimo_dia:
        return date(anio, mes, ultimo_dia)
    return date(anio, mes, inicio.day) - timedelta(days=1)


def inicio_de_periodo(ultimo_fin: date | None, hoy: date) -> date:
    """Si hay un periodo vigente o futuro (último fin >= hoy), el nuevo empieza el día siguiente
    a ese fin; si no (vencido o sin mensualidad), empieza hoy."""
    if ultimo_fin is not None and ultimo_fin >= hoy:
        return ultimo_fin + timedelta(days=1)
    return hoy


def tope_de_adelanto(hoy: date) -> date:
    """Fecha más lejana en que puede terminar un periodo pagado: hoy + 12 meses."""
    return sumar_meses(hoy, MESES_ADELANTO_MAXIMO)


def validar_tope_de_adelanto(fin: date, hoy: date) -> date:
    tope = tope_de_adelanto(hoy)
    if fin > tope:
        raise ValueError(
            f"El pago dejaría la mensualidad vigente hasta el {fin:%d/%m/%Y}: lo máximo es "
            f"{MESES_ADELANTO_MAXIMO} meses desde hoy ({tope:%d/%m/%Y}). Registra menos meses."
        )
    return fin


@dataclass(frozen=True)
class Periodo:
    inicio: date
    fin: date


@dataclass(frozen=True)
class EstadoMensualidad:
    estado: str
    actual: Periodo | None = None
    futuros: list[Periodo] = field(default_factory=list)
    # VIGENTE: fin del último periodo encadenado desde el actual. VENCIDA: fecha en que venció.
    # PAGADA_A_FUTURO: fin del último periodo encadenado desde el primero futuro.
    vence: date | None = None
    dias_restantes: int | None = None    # solo VIGENTE: 0 = vence hoy
    ultimo_fin: date | None = None       # el fin más lejano: de aquí sale el inicio del próximo pago


def _fin_encadenado(desde: Periodo, periodos: list[Periodo]) -> date:
    """Sigue los periodos que continúan sin hueco (empiezan a más tardar el día siguiente al fin)."""
    fin = desde.fin
    for p in sorted(periodos, key=lambda p: p.inicio):
        if p.inicio <= fin + timedelta(days=1) and p.fin > fin:
            fin = p.fin
    return fin


def estado_mensualidad(periodos: list[Periodo], hoy: date) -> EstadoMensualidad:
    """Estado de la mensualidad con los periodos que cuentan (los anulados ya vienen excluidos).

    Vigente si algún periodo cumple inicio <= hoy <= fin (la regla de la Iteración 1).
    """
    if not periodos:
        return EstadoMensualidad(SIN_MENSUALIDAD)
    ultimo_fin = max(p.fin for p in periodos)
    futuros = sorted((p for p in periodos if p.inicio > hoy), key=lambda p: p.inicio)
    actuales = [p for p in periodos if p.inicio <= hoy <= p.fin]
    if actuales:
        actual = max(actuales, key=lambda p: p.fin)
        vence = _fin_encadenado(actual, periodos)
        return EstadoMensualidad(VIGENTE, actual, futuros, vence, (vence - hoy).days, ultimo_fin)
    if futuros:
        return EstadoMensualidad(PAGADA_A_FUTURO, None, futuros, _fin_encadenado(futuros[0], periodos), None,
                                 ultimo_fin)
    return EstadoMensualidad(VENCIDA, None, [], ultimo_fin, None, ultimo_fin)


# --- Monto (D11) y validaciones del pago ---

def _entero(valor: object) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def validar_meses(meses: object) -> int:
    if not _entero(meses) or not MESES_MINIMO <= meses <= MESES_MAXIMO:
        raise ValueError(f"Los meses deben ser un número entero de {MESES_MINIMO} a {MESES_MAXIMO}.")
    return meses


def validar_valor_tarifa(valor: object) -> int:
    if not _entero(valor) or not TARIFA_MINIMA <= valor <= TARIFA_MAXIMA:
        raise ValueError("La tarifa debe ser un valor entero en pesos, sin decimales, entre $ 1.000 y $ 2.000.000.")
    return valor


def formatear_pesos(valor: int) -> str:
    """Formato de RNF-22: 120000 -> '$ 120.000' (pesos enteros, punto como separador de miles)."""
    return f"$ {valor:,}".replace(",", ".")


def calcular_monto(valor_mensual: int, meses: int) -> int:
    """El sistema calcula el monto (D11): tarifa vigente × meses. Quien cobra no lo digita."""
    return validar_valor_tarifa(valor_mensual) * validar_meses(meses)


def validar_tipo_vehiculo(tipo: str) -> str:
    if tipo not in TIPOS_VEHICULO:
        raise ValueError("El tipo de vehículo debe ser MOTO, AUTOMOVIL o CAMIONETA.")
    return tipo


def validar_metodo(metodo: str) -> str:
    if metodo not in METODOS_PAGO:
        raise ValueError("El método de pago debe ser EFECTIVO, TRANSFERENCIA o TARJETA.")
    return metodo


def normalizar_referencia(metodo: str, referencia: str | None) -> str | None:
    """Obligatoria para TRANSFERENCIA y TARJETA (4 a 30 letras, números o guion); vacía en EFECTIVO.

    Se quitan los espacios exteriores; una referencia vacía se guarda como NULL.
    """
    referencia = referencia.strip() if isinstance(referencia, str) else referencia
    if validar_metodo(metodo) == "EFECTIVO":
        if referencia:
            raise ValueError("Un pago en efectivo no lleva referencia: deja el campo vacío.")
        return None
    if not referencia:
        raise ValueError("La referencia es obligatoria para transferencia y tarjeta.")
    if not isinstance(referencia, str) or not PATRON_REFERENCIA.fullmatch(referencia):
        raise ValueError(f"La referencia debe tener de {REFERENCIA_MINIMA} a {REFERENCIA_MAXIMA} caracteres: "
                         "letras, números o guion.")
    return referencia


def validar_motivo_anulacion(motivo: str) -> str:
    """De 10 a 200 caracteres sin contar los espacios del inicio y del final."""
    motivo = motivo.strip() if isinstance(motivo, str) else ""
    if not motivo:
        raise ValueError("El motivo de la anulación es obligatorio.")
    if not MOTIVO_ANULACION_MINIMO <= len(motivo) <= MOTIVO_ANULACION_MAXIMO:
        raise ValueError(f"El motivo debe tener de {MOTIVO_ANULACION_MINIMO} a {MOTIVO_ANULACION_MAXIMO} caracteres.")
    return motivo


# --- Cliente (RF-34) ---

def validar_tipo_documento(tipo: str) -> str:
    if tipo not in TIPOS_DOCUMENTO:
        raise ValueError("El tipo de documento debe ser CC, CE o PA.")
    return tipo


def normalizar_documento(documento: str) -> str:
    """Quita los espacios exteriores, pasa a mayúsculas y exige de 5 a 15 letras o números."""
    documento = documento.strip().upper()
    if not PATRON_DOCUMENTO.fullmatch(documento):
        raise ValueError(f"El número de documento debe tener de {DOCUMENTO_MINIMO} a {DOCUMENTO_MAXIMO} "
                         "caracteres: letras y números, sin espacios ni puntos.")
    return documento


def validar_telefono(telefono: str) -> str:
    telefono = telefono.strip()
    if not PATRON_TELEFONO.fullmatch(telefono):
        raise ValueError("El teléfono debe tener 10 dígitos, sin espacios ni otros caracteres.")
    return telefono


def normalizar_correo(correo: str | None) -> str | None:
    """Opcional: vacío se guarda como NULL. Si se da, debe tener la forma nombre@dominio.ext."""
    if correo is None or not correo.strip():
        return None
    correo = correo.strip()
    if not PATRON_CORREO.fullmatch(correo):
        raise ValueError("El correo no tiene un formato válido (ej. ana@correo.com).")
    return correo
