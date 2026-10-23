from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.celda import CeldaRespuesta
from app.schemas.comun import Identificador
from app.schemas.vehiculo import Placa, VehiculoRespuesta


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
