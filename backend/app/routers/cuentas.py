from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query

from app.domain.permisos import CUENTAS_GESTIONAR
from app.routers.dependencias import DatabaseSession, requiere
from app.schemas.cuenta import CuentaCrear, CuentaDetalle, CuentaRespuesta, CuentasPagina
from app.services import cuenta as service
from app.services.autenticacion import SesionActual

# Iteración 2: solo el Administrador gestiona cuentas. No hay DELETE (D4) ni edición de datos (D6).
router = APIRouter(prefix="/cuentas", tags=["Cuentas de usuario"])
Administrador = Annotated[SesionActual, Depends(requiere(CUENTAS_GESTIONAR))]
CuentaId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.post("", response_model=CuentaRespuesta, status_code=201)
def crear(data: CuentaCrear, session: DatabaseSession, actor: Administrador) -> CuentaRespuesta:
    return service.crear(session, data, actor)


@router.get("", response_model=CuentasPagina)
def listar(
    session: DatabaseSession,
    _: Administrador,
    buscar: Annotated[str | None, Query(max_length=80, description="Parte del nombre o del usuario")] = None,
    rol: Literal["ADMINISTRADOR", "OPERADOR"] | None = None,
    estado: Literal["ACTIVA", "INACTIVA"] | None = None,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CuentasPagina:
    activa = None if estado is None else estado == "ACTIVA"
    return service.listar(session, buscar, rol, activa, offset, limit)


@router.get("/{id}", response_model=CuentaDetalle)
def detalle(id: CuentaId, session: DatabaseSession, _: Administrador) -> CuentaDetalle:
    return service.detalle(session, id)


@router.post("/{id}/desactivar", response_model=CuentaRespuesta)
def desactivar(id: CuentaId, session: DatabaseSession, actor: Administrador) -> CuentaRespuesta:
    return service.desactivar(session, id, actor)


@router.post("/{id}/reactivar", response_model=CuentaRespuesta)
def reactivar(id: CuentaId, session: DatabaseSession, actor: Administrador) -> CuentaRespuesta:
    return service.reactivar(session, id, actor)
