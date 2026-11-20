"""Esquemas de tarifas (Iteración 3, RF-32, RF-33). Una tarifa nunca se edita: cada cambio crea una nueva."""

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from app.domain.pagos import TIPOS_VEHICULO, validar_valor_tarifa

TipoVehiculoTarifa = Literal[TIPOS_VEHICULO]


class TarifaCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo_vehiculo: TipoVehiculoTarifa
    # Entero estricto: 1000.5, "120000" o un valor vacío se rechazan (pesos enteros, RNF-22).
    valor: Annotated[int, Field(strict=True), AfterValidator(validar_valor_tarifa)]


class TarifaRespuesta(BaseModel):
    id: int
    tipo_vehiculo: str
    valor: int
    vigente_desde: datetime
    definida_por: str | None     # "Nombre (usuario)"; None = la definieron las semillas

    @field_validator("vigente_desde")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)


class TarifaVigenteRespuesta(BaseModel):
    """Una fila por tipo de vehículo; tarifa None si el tipo aún no tiene tarifa."""
    tipo_vehiculo: str
    tarifa: TarifaRespuesta | None


class TarifasPagina(BaseModel):
    items: list[TarifaRespuesta]
    total: int
    offset: int
    limit: int
