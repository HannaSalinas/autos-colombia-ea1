"""Hash de contraseñas (bcrypt) y token de sesión firmado (JWT). Sin base de datos.

- bcrypt con costo 12 (RNF-13): cada hash tarda una fracción de segundo a propósito, para que
  adivinar contraseñas por fuerza bruta sea muy lento. La sal va dentro del propio hash.
- El token (RNF-14) lleva el id de la cuenta (`sub`), la versión de sesión (`ver`), cuándo se
  emitió (`iat`) y cuándo vence (`exp`, 8 horas). Va firmado con HS256 y JWT_SECRETO: si alguien
  lo modifica, la firma deja de coincidir. No lleva el rol: el rol se lee siempre de la base.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import bcrypt
import jwt

from app.config import load_auth_settings

COSTO_BCRYPT = 12
DURACION_SESION = timedelta(hours=8)   # un turno
ALGORITMO = "HS256"


def hash_contrasena(contrasena: str) -> str:
    """Hash bcrypt de costo 12. La contraseña debe venir ya validada (máximo 72 bytes)."""
    return bcrypt.hashpw(contrasena.encode("utf-8"), bcrypt.gensalt(rounds=COSTO_BCRYPT)).decode("ascii")


def verificar_contrasena(contrasena: str, hash_guardado: str) -> bool:
    try:
        return bcrypt.checkpw(contrasena.encode("utf-8"), hash_guardado.encode("ascii"))
    except ValueError:
        # Más de 72 bytes o hash dañado: no coincide, nunca un error 500.
        return False


@lru_cache
def hash_de_relleno() -> str:
    """Hash de una clave que nadie usa. Si el usuario no existe se compara contra este hash, para
    que la respuesta tarde lo mismo que con una contraseña incorrecta (D5: no revelar usuarios)."""
    return hash_contrasena("relleno-sin-cuenta-0")


@lru_cache
def secreto() -> str:
    """Se lee una vez por proceso: si falta o es corto, la API no firma ni acepta tokens."""
    return load_auth_settings().jwt_secreto


@dataclass(frozen=True)
class DatosToken:
    cuenta_id: int
    version: int


class TokenInvalido(Exception):
    """Token vencido, mal firmado o con un formato inesperado."""


def crear_token(cuenta_id: int, version: int, ahora: datetime | None = None) -> tuple[str, datetime]:
    ahora = ahora or datetime.now(timezone.utc)
    expira = ahora + DURACION_SESION
    datos = {"sub": str(cuenta_id), "ver": version, "iat": ahora, "exp": expira}
    return jwt.encode(datos, secreto(), algorithm=ALGORITMO), expira


def leer_token(token: str) -> DatosToken:
    """Verifica firma y vencimiento. Solo acepta HS256 (nunca 'none' ni otro algoritmo)."""
    try:
        datos = jwt.decode(token, secreto(), algorithms=[ALGORITMO],
                           options={"require": ["sub", "ver", "iat", "exp"]})
        cuenta_id, version = int(datos["sub"]), datos["ver"]
    except (jwt.PyJWTError, ValueError, TypeError):
        raise TokenInvalido() from None
    if type(version) is not int or not 1 <= cuenta_id <= 9223372036854775807 or not 0 <= version <= 2147483647:
        raise TokenInvalido()
    return DatosToken(cuenta_id=cuenta_id, version=version)
