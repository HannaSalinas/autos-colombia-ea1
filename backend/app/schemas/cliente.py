"""Esquemas de clientes. Iteración 3 (RF-34, D15): el Administrador registra; ambos roles consultan."""

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, field_validator

from app.domain.pagos import TIPOS_DOCUMENTO, normalizar_correo, normalizar_documento, validar_telefono
from app.domain.reglas import validar_nombre_completo

TipoDocumento = Literal[TIPOS_DOCUMENTO]


class ClienteCrear(BaseModel):
    """Las mismas reglas que la base (migración 0009) y Angular (RNF-16)."""
    model_config = ConfigDict(extra="forbid")

    tipo_documento: TipoDocumento
    documento: Annotated[str, AfterValidator(normalizar_documento)]
    nombre: Annotated[str, AfterValidator(validar_nombre_completo)]
    telefono: Annotated[str, AfterValidator(validar_telefono)]
    correo: Annotated[str | None, AfterValidator(normalizar_correo)] = None


class VehiculoDelCliente(BaseModel):
    id: int
    placa: str
    tipo: str


class ClienteRespuesta(BaseModel):
    id: int
    tipo_documento: str
    documento: str
    nombre: str
    telefono: str
    correo: str | None
    # D18: quién y cuándo lo registró. None = anterior a la Iteración 3 o creado por las semillas.
    registrado_en: datetime | None
    registrado_por: str | None
    vehiculos: list[VehiculoDelCliente]

    @field_validator("registrado_en")
    @classmethod
    def utc(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(timezone.utc) if value is not None else None


class ClientesPagina(BaseModel):
    items: list[ClienteRespuesta]
    total: int
    offset: int
    limit: int
