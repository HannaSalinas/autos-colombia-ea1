from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, field_validator

from app.domain.reglas import DESCRIPCION_MAXIMA, MOTIVO_MAXIMO, validar_texto_corto
from app.schemas.celda import CeldaRespuesta
from app.schemas.comun import Identificador
from app.schemas.vehiculo import Placa, VehiculoRespuesta


class EntradaCrear(BaseModel):
    """Iteración 1: el operador ya no elige la celda; la asigna el sistema."""
    model_config = ConfigDict(extra="forbid")
    placa: Placa
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


class MovimientoRespuesta(EstanciaRespuesta):
    """Respuesta de entrada y salida: placa, celda asignada y, al salir, la permanencia."""
    placa: str
    celda: CeldaRespuesta
    duracion_segundos: int | None
    permanencia: str | None


class EstadoVehiculoRespuesta(BaseModel):
    vehiculo: VehiculoRespuesta
    esta_dentro: bool
    estancia: EstanciaAbiertaRespuesta | None



# --- Corrección de celda y novedades (Fase 3) ---

def texto_corto(maximo: int, campo: str) -> BeforeValidator:
    # Si no llega un texto, Pydantic responde 422 por el tipo.
    return BeforeValidator(lambda v: validar_texto_corto(v, maximo, campo) if isinstance(v, str) else v)


Motivo = Annotated[str, texto_corto(MOTIVO_MAXIMO, "motivo")]
Descripcion = Annotated[str, texto_corto(DESCRIPCION_MAXIMA, "descripción")]
TipoNovedad = Literal["RAYON", "GOLPE", "OBJETO_OLVIDADO", "OTRO"]


class CorreccionCrear(BaseModel):
    """El conductor parqueó en otra celda: el operador la corrige dejando el motivo."""
    model_config = ConfigDict(extra="forbid")
    celda_id: Identificador
    operador_id: Identificador
    motivo: Motivo


class CorreccionRespuesta(BaseModel):
    id: int
    estancia_id: int
    celda_anterior: CeldaRespuesta
    celda_nueva: CeldaRespuesta
    operador_id: int
    fecha: datetime
    motivo: str

    @field_validator("fecha")
    @classmethod
    def fecha_utc(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)


class NovedadCrear(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: TipoNovedad
    descripcion: Descripcion
    operador_id: Identificador


class NovedadRespuesta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    estancia_id: int
    operador_id: int
    fecha: datetime
    tipo: str
    descripcion: str

    @field_validator("fecha")
    @classmethod
    def fecha_utc(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)
