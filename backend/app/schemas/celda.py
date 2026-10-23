from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, field_validator

from app.models import required_text

Texto = Annotated[str, BeforeValidator(lambda value: required_text(value, "El campo"))]
Codigo = Annotated[Texto, AfterValidator(str.upper)]
# Iteración 1: el tipo dejó de ser texto libre. MOTO o CARRO (automóvil y camioneta usan CARRO).
TipoCelda = Annotated[
    Literal["MOTO", "CARRO"],
    BeforeValidator(lambda value: required_text(value, "tipo").upper() if isinstance(value, str) else value),
]


class CeldaCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: Codigo
    tipo: TipoCelda


class CeldaActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo: Codigo | None = None
    tipo: TipoCelda | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Los campos enviados no pueden ser nulos.")
        return value


class CeldaRespuesta(BaseModel):
    """Describe la celda guardada (no revalida: puede haber celdas antiguas de otro tipo)."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    tipo: str
    disponible_desde: datetime | None = None


class CeldasPagina(BaseModel):
    items: list[CeldaRespuesta]
    total: int
    offset: int
    limit: int
