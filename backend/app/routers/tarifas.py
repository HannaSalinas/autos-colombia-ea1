from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.domain.permisos import TARIFAS_GESTIONAR, TARIFAS_VER
from app.routers.dependencias import DatabaseSession, Sesion, requiere
from app.schemas.tarifa import TarifaCrear, TarifaRespuesta, TarifasPagina, TarifaVigenteRespuesta, TipoVehiculoTarifa
from app.services import tarifa as service

# Iteración 3: ambos roles ven la tarifa vigente (HU-26); solo el Administrador ve el historial y
# define una tarifa nueva (HU-27). Una tarifa nunca se edita ni se elimina: no hay PATCH ni DELETE.
router = APIRouter(prefix="/tarifas", tags=["Tarifas"], dependencies=[Depends(requiere(TARIFAS_VER))])
Gestionar = [Depends(requiere(TARIFAS_GESTIONAR))]


@router.get("", response_model=list[TarifaVigenteRespuesta])
def vigentes(session: DatabaseSession):
    return service.vigentes(session)


@router.get("/historial", response_model=TarifasPagina, dependencies=Gestionar)
def historial(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    tipo: TipoVehiculoTarifa | None = None,
):
    return service.historial(session, offset, limit, tipo)


@router.post("", response_model=TarifaRespuesta, status_code=201, dependencies=Gestionar)
def crear(data: TarifaCrear, session: DatabaseSession, sesion: Sesion):
    return service.crear(session, data, sesion)
