"""Inicio de sesión, sesión actual y cierre de sesión (RF-19, RF-21, RF-22, RNF-14, RNF-15).

Códigos de respuesta:
- 401: credenciales inválidas, o sesión ausente, vencida, revocada o de una cuenta desactivada.
- 403: la cuenta está desactivada al iniciar sesión (solo si la contraseña es correcta), o el rol
  no tiene permiso para la operación.
"""

from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.permisos import permisos_de
from app.models import CuentaUsuario, Operador
from app.schemas.autenticacion import CuentaSesion, LoginRespuesta
from app.services.seguridad import TokenInvalido, crear_token, hash_de_relleno, leer_token, verificar_contrasena

CREDENCIALES_INVALIDAS = "Usuario o contraseña inválidos."
CUENTA_DESACTIVADA = "Tu cuenta está desactivada. Contacta al administrador."
SIN_SESION = "Debes iniciar sesión para continuar."
SESION_VENCIDA = "Tu sesión venció o fue cerrada. Ingresa de nuevo."
SIN_PERMISO = "No tienes permiso para esta operación."
SIN_BASE = "No se pudo completar la operación con la base de datos."


class AutenticacionError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class SesionActual:
    """Quién hizo la solicitud. Son datos simples (no un objeto del ORM) para poder cerrar la
    transacción de lectura antes de que el servicio de la operación abra la suya."""
    cuenta_id: int
    operador_id: int        # la persona: responsable de entradas, salidas, correcciones y novedades
    nombre_usuario: str
    nombre: str
    rol: str
    version_sesion: int

    @property
    def permisos(self) -> frozenset[str]:
        return permisos_de(self.rol)

    def como_respuesta(self) -> CuentaSesion:
        return CuentaSesion(id=self.cuenta_id, nombre_usuario=self.nombre_usuario, nombre=self.nombre,
                            rol=self.rol, permisos=sorted(self.permisos))


def _datos_cuenta(session: Session, condicion) -> tuple | None:
    """Lee la cuenta y el nombre de su persona y cierra la lectura (commit de solo lectura).

    Se usa commit y no rollback: en las pruebas, la sesión trabaja sobre un savepoint y un rollback
    descartaría los datos preparados por la prueba.
    """
    try:
        fila = session.execute(
            select(CuentaUsuario.id, CuentaUsuario.operador_id, CuentaUsuario.nombre_usuario, CuentaUsuario.rol,
                   CuentaUsuario.activa, CuentaUsuario.version_sesion, CuentaUsuario.hash_contrasena,
                   Operador.nombre)
            .join(Operador, Operador.id == CuentaUsuario.operador_id).where(condicion)
        ).one_or_none()
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise AutenticacionError(503, SIN_BASE) from None
    return fila


def _sesion(fila) -> SesionActual:
    return SesionActual(cuenta_id=fila.id, operador_id=fila.operador_id, nombre_usuario=fila.nombre_usuario,
                        nombre=fila.nombre, rol=fila.rol, version_sesion=fila.version_sesion)


def iniciar_sesion(session: Session, usuario: str, contrasena: str) -> LoginRespuesta:
    """`usuario` ya normalizado (sin espacios exteriores y en minúsculas)."""
    fila = _datos_cuenta(session, func.lower(CuentaUsuario.nombre_usuario) == usuario)
    if fila is None:
        # Mismo trabajo y mismo mensaje que con una contraseña incorrecta: no revela si el usuario existe.
        verificar_contrasena(contrasena, hash_de_relleno())
        raise AutenticacionError(401, CREDENCIALES_INVALIDAS)
    if not verificar_contrasena(contrasena, fila.hash_contrasena):
        raise AutenticacionError(401, CREDENCIALES_INVALIDAS)
    # Solo con la contraseña correcta se dice que la cuenta está desactivada (HU-15.4).
    if not fila.activa:
        raise AutenticacionError(403, CUENTA_DESACTIVADA)
    sesion = _sesion(fila)
    token, expira = crear_token(sesion.cuenta_id, sesion.version_sesion)
    return LoginRespuesta(token=token, expira_en=expira, cuenta=sesion.como_respuesta())


def sesion_desde_token(session: Session, token: str | None) -> SesionActual:
    """En cada solicitud: firma, vencimiento, cuenta activa y versión de sesión vigente (RNF-14)."""
    if not token:
        raise AutenticacionError(401, SIN_SESION)
    try:
        datos = leer_token(token)
    except TokenInvalido:
        raise AutenticacionError(401, SESION_VENCIDA) from None
    fila = _datos_cuenta(session, CuentaUsuario.id == datos.cuenta_id)
    # Cuenta inexistente o desactivada, o token de antes de desactivarla o de cerrar sesión.
    if fila is None or not fila.activa or fila.version_sesion != datos.version:
        raise AutenticacionError(401, SESION_VENCIDA)
    return _sesion(fila)


def cerrar_sesion(session: Session, sesion: SesionActual) -> None:
    """Sube la versión de sesión: este token (y cualquier otro de la misma cuenta) deja de valer."""
    try:
        session.execute(update(CuentaUsuario)
                        .where(CuentaUsuario.id == sesion.cuenta_id,
                               CuentaUsuario.version_sesion == sesion.version_sesion)
                        .values(version_sesion=CuentaUsuario.version_sesion + 1))
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise AutenticacionError(503, SIN_BASE) from None
