from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, field_validator, model_validator

from app.domain.reglas import normalizar_codigo_celda, normalizar_ubicacion, required_text, validar_codigo_celda

Texto = Annotated[str, BeforeValidator(lambda value: required_text(value, "El campo"))]
# Iteración 2: el código se normaliza (espacios exteriores y mayúsculas) antes de validar: ' c05 ' -> 'C05'.
Codigo = Annotated[Texto, BeforeValidator(lambda v: normalizar_codigo_celda(v) if isinstance(v, str) else v)]
# Iteración 1: el tipo dejó de ser texto libre. MOTO o CARRO (automóvil y camioneta usan CARRO).
TipoCelda = Annotated[
    Literal["MOTO", "CARRO"],
    BeforeValidator(lambda value: required_text(value, "tipo").upper() if isinstance(value, str) else value),
]
# Opcional, hasta 60 caracteres; vacía se guarda como NULL.
Ubicacion = Annotated[str | None, BeforeValidator(lambda v: normalizar_ubicacion(v) if isinstance(v, str) else v)]
EstadoCelda = Literal["LIBRE", "OCUPADA", "INHABILITADA"]


class CeldaCrear(BaseModel):
    """RF-28: código y tipo obligatorios; ubicación opcional. La celda queda libre y habilitada."""
    model_config = ConfigDict(extra="forbid")
    codigo: Codigo
    tipo: TipoCelda
    ubicacion: Ubicacion = None

    @model_validator(mode="after")
    def codigo_segun_tipo(self) -> "CeldaCrear":
        # C01–C99 para CARRO y M01–M99 para MOTO (misma regla que el CHECK ck_celda_codigo_formato).
        validar_codigo_celda(self.codigo, self.tipo)
        return self


class CeldaActualizar(BaseModel):
    """RF-29: la ubicación siempre; el código y el tipo solo si la celda nunca tuvo movimientos (D8).
    Como el cambio puede ser parcial, la combinación final de código y tipo la valida el servicio."""
    model_config = ConfigDict(extra="forbid")
    codigo: Codigo | None = None
    tipo: TipoCelda | None = None
    ubicacion: Ubicacion = None

    @field_validator("codigo", "tipo", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Los campos enviados no pueden ser nulos.")
        return value


class CeldaRespuesta(BaseModel):
    """Describe la celda guardada (no revalida: puede haber celdas antiguas de otro tipo).
    Es la celda que aparece dentro de las estancias, correcciones y reportes."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    tipo: str
    disponible_desde: datetime | None = None
    ubicacion: str | None = None
    habilitada: bool = True


class CeldaGestion(CeldaRespuesta):
    """Celda en la gestión de celdas (RF-27): estado calculado, placa si está ocupada y si tiene
    historial (D8: entonces su código y su tipo ya no se pueden cambiar)."""
    estado: EstadoCelda
    placa: str | None
    tiene_historial: bool


class CeldasPagina(BaseModel):
    items: list[CeldaGestion]
    total: int
    offset: int
    limit: int


class EventoAuditoriaCelda(BaseModel):
    fecha: datetime
    accion: str
    detalle: str | None
    actor: str | None   # nombre y usuario; None = el sistema

    @field_validator("fecha")
    @classmethod
    def fecha_utc(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)


class CeldaDetalle(CeldaGestion):
    """RF-31: quién y cuándo creó, editó, inhabilitó o rehabilitó la celda."""
    auditoria: list[EventoAuditoriaCelda]
