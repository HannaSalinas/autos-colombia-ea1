"""Esquemas de pagos de mensualidad (Iteración 3, RF-35 a RF-38).

El responsable del pago nunca se recibe: es la cuenta de la sesión (RF-36). El monto tampoco se
digita: lo calcula el sistema (D11); el cliente solo envía el monto que vio en el resumen
(monto_confirmado) para detectar que la tarifa cambió entre el resumen y la confirmación.
"""

from datetime import date, datetime, timezone
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.pagos import (
    MESES_MAXIMO, MESES_MINIMO, METODOS_PAGO, normalizar_referencia, validar_meses, validar_motivo_anulacion,
)
from app.schemas.vehiculo import Placa

Meses = Annotated[int, Field(strict=True), AfterValidator(validar_meses)]
MetodoPago = Literal[METODOS_PAGO]
EstadoPago = Literal["VALIDO", "ANULADO"]


class PagoCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    placa: Placa
    meses: Meses
    metodo: MetodoPago
    referencia: str | None = None
    # Lo que vio quien cobra en el resumen (RNF-27). Si la tarifa cambió, el registro se rechaza.
    monto_confirmado: Annotated[int, Field(strict=True, ge=1)]

    @model_validator(mode="after")
    def referencia_segun_metodo(self) -> "PagoCrear":
        self.referencia = normalizar_referencia(self.metodo, self.referencia)
        return self


class AnulacionCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motivo: Annotated[str, AfterValidator(validar_motivo_anulacion)]


def _utc(value: datetime | None) -> datetime | None:
    return value.astimezone(timezone.utc) if value is not None else None


class PeriodoRespuesta(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    comprobante: str | None      # None = periodo anterior a la Iteración 3, sin pago (D10)


class ClienteResumen(BaseModel):
    id: int
    tipo_documento: str
    documento: str
    nombre: str
    telefono: str


class TarifaVigente(BaseModel):
    id: int
    tipo_vehiculo: str
    valor: int


class EstadoMensualidadRespuesta(BaseModel):
    """RF-35, HU-29: lo que ve quien cobra al buscar una placa."""
    vehiculo_id: int
    placa: str
    tipo_vehiculo: str
    marca: str
    color: str
    cliente: ClienteResumen
    estado: Literal["VIGENTE", "VENCIDA", "SIN_MENSUALIDAD", "PAGADA_A_FUTURO"]
    periodo_actual: PeriodoRespuesta | None
    periodos_futuros: list[PeriodoRespuesta]
    # Se muestran marcados como anulados, pero no cuentan para el estado (HU-29 criterio 3, caso ME-04).
    periodos_anulados: list[PeriodoRespuesta]
    vence: date | None
    dias_restantes: int | None
    # Para registrar un pago: inicio que tendría (D13), fin máximo permitido (hoy + 12 meses) y tarifa.
    inicio_nuevo_periodo: date
    fin_maximo: date
    tarifa: TarifaVigente | None


class CotizacionRespuesta(BaseModel):
    """El resumen que se confirma antes de registrar (RNF-27). No guarda nada."""
    placa: str
    cliente_nombre: str
    tipo_vehiculo: str
    meses: int = Field(ge=MESES_MINIMO, le=MESES_MAXIMO)
    fecha_inicio: date
    fecha_fin: date
    tarifa_id: int
    valor_mensual: int
    monto: int


class PagoResumen(BaseModel):
    """Una fila del listado de pagos (RF-37)."""
    id: int
    comprobante: str
    fecha: datetime
    placa: str
    cliente_nombre: str
    fecha_inicio: date
    fecha_fin: date
    meses: int
    monto: int
    metodo: str
    estado: EstadoPago
    registrado_por: str

    @field_validator("fecha")
    @classmethod
    def fecha_utc(cls, value: datetime) -> datetime:
        return _utc(value)


class PagoDetalle(PagoResumen):
    """El comprobante (RF-37) y, si se anuló, quién, cuándo y por qué (RF-38)."""
    vehiculo_id: int
    tipo_vehiculo: str
    cliente_tipo_documento: str
    cliente_documento: str
    valor_mensual: int
    referencia: str | None
    anulado_en: datetime | None
    anulado_por: str | None
    motivo_anulacion: str | None
    # Solo se anula el pago VÁLIDO del último periodo del vehículo (D14).
    anulable: bool

    @field_validator("anulado_en")
    @classmethod
    def anulado_utc(cls, value: datetime | None) -> datetime | None:
        return _utc(value)


class PagosPagina(BaseModel):
    items: list[PagoResumen]
    total: int
    offset: int
    limit: int
