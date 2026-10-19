from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from app.models import required_text


Texto = Annotated[str, BeforeValidator(lambda value: required_text(value, "El campo"))]
Placa = Annotated[Texto, AfterValidator(str.upper)]
Anio = Annotated[int, Field(strict=True, ge=1, le=9999)]
TipoVehiculo = Annotated[
    Literal["MOTO", "AUTOMOVIL", "CAMIONETA"],
    BeforeValidator(lambda value: required_text(value, "tipo")),
]


class VehiculoCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    placa: Placa
    color: Texto
    modelo: Anio
    marca: Texto
    tipo: TipoVehiculo


class VehiculoActualizar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    placa: Placa | None = None
    color: Texto | None = None
    modelo: Anio | None = None
    marca: Texto | None = None
    tipo: TipoVehiculo | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Los campos enviados no pueden ser nulos.")
        return value


class VehiculoRespuesta(VehiculoCrear):
    model_config = ConfigDict(from_attributes=True, extra="forbid")
    id: int


class VehiculosPagina(BaseModel):
    items: list[VehiculoRespuesta]
    total: int
    offset: int
    limit: int
