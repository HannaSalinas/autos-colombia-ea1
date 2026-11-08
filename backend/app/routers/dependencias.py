"""Dependencias compartidas por los routers: sesión de base de datos, sesión del usuario y permisos.

Los routers no tienen lógica: solo declaran qué permiso exige cada endpoint con `requiere(...)`.
El permiso se busca en app.domain.permisos, el único mapa de rol a permisos.
"""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_session
from app.domain.permisos import tiene_permiso
from app.services.autenticacion import SIN_PERMISO, AutenticacionError, SesionActual, sesion_desde_token

DatabaseSession = Annotated[Session, Depends(get_session)]

# auto_error=False: sin encabezado (o con otro esquema) respondemos nosotros, con 401 y en español.
esquema_bearer = HTTPBearer(auto_error=False, description="Token de POST /auth/login")


def sesion_actual(
    credenciales: Annotated[HTTPAuthorizationCredentials | None, Depends(esquema_bearer)],
    session: DatabaseSession,
) -> SesionActual:
    return sesion_desde_token(session, credenciales.credentials if credenciales else None)


Sesion = Annotated[SesionActual, Depends(sesion_actual)]


def requiere(permiso: str):
    """Dependencia que exige un permiso: 401 sin sesión válida, 403 si el rol no lo tiene."""
    def comprobar(sesion: Sesion) -> SesionActual:
        if not tiene_permiso(sesion.rol, permiso):
            raise AutenticacionError(403, SIN_PERMISO)
        return sesion
    comprobar.__name__ = f"requiere_{permiso.replace(':', '_')}"
    return comprobar
