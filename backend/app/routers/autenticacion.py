from fastapi import APIRouter, Response

from app.routers.dependencias import DatabaseSession, Sesion
from app.schemas.autenticacion import CuentaSesion, LoginEntrada, LoginRespuesta
from app.services import autenticacion as service

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/login", response_model=LoginRespuesta)
def login(data: LoginEntrada, session: DatabaseSession) -> LoginRespuesta:
    """Única operación pública (junto con /health). El rol nunca se elige: es el de la cuenta (D1)."""
    return service.iniciar_sesion(session, data.usuario_normalizado(), data.contrasena)


@router.get("/yo", response_model=CuentaSesion)
def yo(sesion: Sesion) -> CuentaSesion:
    """La cuenta con sesión y sus permisos: con esta lista el frontend arma el menú (D2)."""
    return sesion.como_respuesta()


@router.post("/cerrar-sesion", status_code=204)
def cerrar_sesion(sesion: Sesion, session: DatabaseSession) -> Response:
    service.cerrar_sesion(session, sesion)
    return Response(status_code=204)
