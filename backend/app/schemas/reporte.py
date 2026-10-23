from datetime import datetime, timezone

from pydantic import BaseModel, field_validator


def utc(value: datetime | None) -> datetime | None:
    return value.astimezone(timezone.utc) if value is not None else None


class CeldasPorTipo(BaseModel):
    tipo: str
    total: int
    ocupadas: int
    libres: int


class VehiculoDentro(BaseModel):
    estancia_id: int
    placa: str
    tipo_vehiculo: str
    celda: str
    entrada: datetime
    operador_entrada: str
    tiempo: str  # permanencia hasta ahora, ej. "2 h 15 min"

    @field_validator("entrada")
    @classmethod
    def entrada_utc(cls, value: datetime) -> datetime:
        return utc(value)


class OcupacionRespuesta(BaseModel):
    generado: datetime
    celdas: list[CeldasPorTipo]
    dentro: list[VehiculoDentro]


class EstanciaHistorial(BaseModel):
    id: int
    placa: str
    tipo_vehiculo: str
    celda: str
    entrada: datetime
    salida: datetime | None
    abierta: bool
    duracion_segundos: int | None
    permanencia: str | None
    operador_entrada: str
    operador_salida: str | None
    novedades: int
    correcciones: int

    @field_validator("entrada", "salida")
    @classmethod
    def fechas_utc(cls, value: datetime | None) -> datetime | None:
        return utc(value)


class HistorialPagina(BaseModel):
    items: list[EstanciaHistorial]
    total: int
    offset: int
    limit: int
