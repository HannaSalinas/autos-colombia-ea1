from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.celda import CeldaRespuesta
from app.schemas.vehiculo import Placa, VehiculoRespuesta

Identificador = Annotated[int, Field(strict=True, ge=1, le=9223372036854775807)]


class EntradaCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    placa: Placa
    celda_id: Identificador
    operador_id: Identificador


class SalidaCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    placa: Placa
    operador_id: Identificador


class EstanciaRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    vehiculo_id: int
    celda_id: int
    entrada: datetime
    salida: datetime | None
    operador_entrada_id: int
    operador_salida_id: int | None

    @field_validator("entrada", "salida")
    @classmethod
    def fechas_utc(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(timezone.utc) if value is not None else None


class EstanciaAbiertaRespuesta(EstanciaRespuesta):
    celda: CeldaRespuesta


class EstadoVehiculoRespuesta(BaseModel):
    vehiculo: VehiculoRespuesta
    esta_dentro: bool
    estancia: EstanciaAbiertaRespuesta | None
