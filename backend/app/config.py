"""Configuración privada desde backend/.env y variables de entorno."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class ConfigurationError(ValueError):
    """Error que contiene únicamente nombres de variables, nunca sus valores."""


@dataclass(frozen=True)
class DatabaseSettings:
    host: str
    port: int
    name: str = field(repr=False)
    user: str = field(repr=False)
    password: str = field(repr=False)
    connect_timeout: int = 5


def load_database_settings() -> DatabaseSettings:
    # No interpolar $ ni ${...} dentro de las contraseñas.
    values = {**dotenv_values(ENV_FILE, encoding="utf-8-sig", interpolate=False), **os.environ}
    required = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_CONNECT_TIMEOUT")
    missing = [
        key for key in required
        if not (values.get(key) or "").strip()
        or (values.get(key) or "").startswith("CAMBIAR_")
    ]
    if missing:
        raise ConfigurationError("Completa en backend/.env: " + ", ".join(missing))

    def positive_integer(key: str, maximum: int) -> int:
        try:
            number = int(values[key])
        except (ValueError, TypeError):
            raise ConfigurationError(f"{key} debe ser un entero válido.") from None
        if not 1 <= number <= maximum:
            raise ConfigurationError(f"{key} debe estar entre 1 y {maximum}.")
        return number

    return DatabaseSettings(
        host=values["DB_HOST"],
        port=positive_integer("DB_PORT", 65535),
        name=values["DB_NAME"],
        user=values["DB_USER"],
        password=values["DB_PASSWORD"],
        connect_timeout=positive_integer("DB_CONNECT_TIMEOUT", 60),
    )


# --- Iteración 2: sesión con token firmado ---

SECRETO_MINIMO = 32


@dataclass(frozen=True)
class AuthSettings:
    jwt_secreto: str = field(repr=False)


def load_auth_settings() -> AuthSettings:
    """Clave con la que se firman los tokens. Va solo en .env (nunca en el repositorio)."""
    values = {**dotenv_values(ENV_FILE, encoding="utf-8-sig", interpolate=False), **os.environ}
    secreto = (values.get("JWT_SECRETO") or "").strip()
    if not secreto or secreto.startswith("CAMBIAR_"):
        raise ConfigurationError("Completa en .env: JWT_SECRETO")
    if len(secreto) < SECRETO_MINIMO:
        raise ConfigurationError(f"JWT_SECRETO debe tener al menos {SECRETO_MINIMO} caracteres.")
    return AuthSettings(jwt_secreto=secreto)


# --- Iteración 2: cuentas semilla (RNF-13: las contraseñas solo viven en .env) ---

@dataclass(frozen=True)
class CredencialesSemilla:
    admin_usuario: str
    admin_nombre: str
    admin_contrasena: str = field(repr=False)
    marta_contrasena: str = field(repr=False)
    diego_contrasena: str = field(repr=False)


def load_seed_credentials() -> CredencialesSemilla:
    """Lee y valida las credenciales de las cuentas semilla. Los errores nombran la variable, nunca su valor."""
    from app.domain.reglas import validar_contrasena, validar_nombre_completo, validar_nombre_usuario

    values = {**dotenv_values(ENV_FILE, encoding="utf-8-sig", interpolate=False), **os.environ}
    requeridas = ("ADMIN_USUARIO", "ADMIN_NOMBRE", "ADMIN_CONTRASENA", "MARTA_CONTRASENA", "DIEGO_CONTRASENA")
    faltan = [k for k in requeridas if not (values.get(k) or "").strip() or (values.get(k) or "").startswith("CAMBIAR_")]
    if faltan:
        raise ConfigurationError("Completa en .env: " + ", ".join(faltan))
    reglas = {"ADMIN_USUARIO": validar_nombre_usuario, "ADMIN_NOMBRE": validar_nombre_completo,
              "ADMIN_CONTRASENA": validar_contrasena, "MARTA_CONTRASENA": validar_contrasena,
              "DIEGO_CONTRASENA": validar_contrasena}
    validos = {}
    for clave, regla in reglas.items():
        try:
            validos[clave] = regla(values[clave])
        except ValueError as error:
            raise ConfigurationError(f"{clave} no es válida: {error}") from None
    if validos["ADMIN_USUARIO"] in {"marta.usuga", "diego.arango"}:
        raise ConfigurationError("ADMIN_USUARIO no puede ser el usuario de Marta ni el de Diego.")
    return CredencialesSemilla(
        admin_usuario=validos["ADMIN_USUARIO"], admin_nombre=validos["ADMIN_NOMBRE"],
        admin_contrasena=validos["ADMIN_CONTRASENA"], marta_contrasena=validos["MARTA_CONTRASENA"],
        diego_contrasena=validos["DIEGO_CONTRASENA"],
    )
