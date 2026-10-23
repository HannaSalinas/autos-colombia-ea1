from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.database import get_session
from app.schemas.cliente import ClienteRespuesta, ClientesPagina
from app.schemas.vehiculo import VehiculoDetalle
from app.services import cliente as service

router = APIRouter(prefix="/clientes", tags=["Clientes"])
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
