from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_session
from app.domain.permisos import VEHICULOS_VER
from app.routers.dependencias import requiere
from app.schemas.cliente import ClienteRespuesta, ClientesPagina
from app.schemas.vehiculo import VehiculoDetalle
from app.services import cliente as service

# Solo lectura; se consultan junto con los vehículos (Iteración 2: ambos roles).
router = APIRouter(prefix="/clientes", tags=["Clientes"], dependencies=[Depends(requiere(VEHICULOS_VER))])
DatabaseSession = Annotated[Session, Depends(get_session)]
ClientId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.get("", response_model=ClientesPagina)
def list_all(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return service.list_clients(session, offset, limit)


@router.get("/{id}", response_model=ClienteRespuesta)
def get_one(id: ClientId, session: DatabaseSession):
    return service.get_client(session, id)


@router.get("/{id}/vehiculos", response_model=list[VehiculoDetalle])
def vehicles(id: ClientId, session: DatabaseSession):
    return service.list_client_vehicles(session, id)
