from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from app.domain.reglas import MODELO_MINIMO, hoy_bogota, normalizar_placa, validar_modelo, validar_placa
from app.models import required_text
from app.schemas.comun import Identificador


Texto = Annotated[str, BeforeValidator(lambda value: required_text(value, "El campo"))]
# Sin espacios ni guiones y en mayúsculas. El formato según el tipo se valida aparte.
Placa = Annotated[Texto, AfterValidator(normalizar_placa)]
# El tope (año actual + 1) se calcula en cada solicitud con la fecha de Bogotá.
Anio = Annotated[int, Field(strict=True, ge=MODELO_MINIMO),
                 AfterValidator(lambda anio: validar_modelo(anio, hoy_bogota()))]
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
    cliente_id: Identificador

    @model_validator(mode="after")
    def placa_segun_tipo(self) -> "VehiculoCrear":
        validar_placa(self.placa, self.tipo)
        return self


class VehiculoActualizar(BaseModel):
    """Campos opcionales: el formato de placa con el tipo final lo valida el servicio."""
    model_config = ConfigDict(extra="forbid")

    placa: Placa | None = None
    color: Texto | None = None
    modelo: Anio | None = None
    marca: Texto | None = None
    tipo: TipoVehiculo | None = None
    cliente_id: Identificador | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Los campos enviados no pueden ser nulos.")
        return value


class VehiculoRespuesta(BaseModel):
    """Datos guardados del vehículo. No revalida reglas: solo describe la respuesta."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    placa: str
    color: str
    modelo: int
    marca: str
    tipo: str
    cliente_id: int


class VehiculoDetalle(VehiculoRespuesta):
    """Respuesta de /vehiculos: agrega el dueño y el estado de su mensualidad."""
    cliente_nombre: str
    mensualidad_vigente: bool
    # Vigente: fecha en que vence. Vencida: fecha en que venció. None: nunca ha pagado.
    mensualidad_hasta: date | None
    # Inicio de una mensualidad pagada que todavía no empieza (ej. empieza mañana).
    mensualidad_proxima: date | None


class VehiculosPagina(BaseModel):
    items: list[VehiculoDetalle]
    total: int
    offset: int
    limit: int
