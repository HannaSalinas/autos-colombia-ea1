from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Operador
from app.schemas.operador import OperadorActualizar, OperadorCrear, OperadorRespuesta, OperadoresPagina
from app.services import operador as service

router = APIRouter(prefix="/operadores", tags=["Operadores"])
DatabaseSession = Annotated[Session, Depends(get_session)]
OperatorId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.post("", response_model=OperadorRespuesta, status_code=201)
def create(data: OperadorCrear, session: DatabaseSession) -> Operador:
    return service.create_operator(session, data)


@router.get("", response_model=OperadoresPagina)
def list_all(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict:
    return service.list_operators(session, offset, limit)


@router.get("/{id}", response_model=OperadorRespuesta)
def get_one(id: OperatorId, session: DatabaseSession) -> Operador:
    return service.get_operator(session, id)


@router.patch("/{id}", response_model=OperadorRespuesta)
def update(id: OperatorId, data: OperadorActualizar, session: DatabaseSession) -> Operador:
    return service.update_operator(session, id, data)


@router.delete("/{id}", status_code=204)
def delete(id: OperatorId, session: DatabaseSession) -> Response:
    service.delete_operator(session, id)
    return Response(status_code=204)

