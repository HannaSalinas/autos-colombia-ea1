"""Cuentas de usuario (Iteración 2: HU-19, HU-20, HU-21, RF-31). La contraseña nunca sale en una respuesta."""

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, field_validator

from app.domain.reglas import validar_contrasena, validar_nombre_completo, validar_nombre_usuario

Rol = Literal["ADMINISTRADOR", "OPERADOR"]


def con_regla(regla):
    # Si no llega un texto, Pydantic responde 422 por el tipo.
    return BeforeValidator(lambda v: regla(v) if isinstance(v, str) else v)


class CuentaCrear(BaseModel):
    """Nombre completo de la persona, usuario, contraseña inicial y rol (RF-24). Se crea activa."""
    model_config = ConfigDict(extra="forbid")
    nombre: Annotated[str, con_regla(validar_nombre_completo)]
    # Se normaliza (espacios exteriores y minúsculas) antes de validar: ' Marta.Usuga ' -> 'marta.usuga'.
    nombre_usuario: Annotated[str, con_regla(validar_nombre_usuario)]
    contrasena: Annotated[str, con_regla(validar_contrasena)]
    rol: Rol


class CuentaRespuesta(BaseModel):
    id: int
    nombre: str
    nombre_usuario: str
    rol: str
    activa: bool
    creada_en: datetime

    @field_validator("creada_en")
    @classmethod
    def fecha_utc(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)


class CuentasPagina(BaseModel):
    items: list[CuentaRespuesta]
    total: int
    offset: int
    limit: int


class EventoAuditoria(BaseModel):
    fecha: datetime
    accion: str
    detalle: str | None
    # Nombre y usuario de quien lo hizo; None = el sistema (semillas).
    actor: str | None

    @field_validator("fecha")
    @classmethod
    def fecha_utc(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)


class CuentaDetalle(CuentaRespuesta):
    """RF-31: quién y cuándo creó, desactivó o reactivó la cuenta."""
    auditoria: list[EventoAuditoria]
