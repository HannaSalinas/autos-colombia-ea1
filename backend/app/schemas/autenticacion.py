from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.domain.reglas import normalizar_usuario


def obligatorio(campo: str):
    """Texto no vacío. En el login no se revisa la política de contraseñas: una clave que no la
    cumple simplemente no coincide (401), sin dar pistas."""
    def validar(valor):
        if isinstance(valor, str) and not valor.strip():
            raise ValueError(f"Escribe {campo}.")
        return valor
    return BeforeValidator(validar)


class LoginEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Límites amplios solo para no procesar textos enormes; no revelan la política.
    usuario: Annotated[str, obligatorio("el usuario"), Field(max_length=100)]
    contrasena: Annotated[str, obligatorio("la contraseña"), Field(max_length=200)]

    def usuario_normalizado(self) -> str:
        return normalizar_usuario(self.usuario)


class CuentaSesion(BaseModel):
    """Lo que el frontend necesita de la cuenta con sesión: nunca el hash ni la versión de sesión."""
    id: int
    nombre_usuario: str
    nombre: str
    rol: Literal["ADMINISTRADOR", "OPERADOR"]
    permisos: list[str]


class LoginRespuesta(BaseModel):
    token: str
    tipo: Literal["bearer"] = "bearer"
    expira_en: datetime
    cuenta: CuentaSesion
