from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.domain.permisos import CUENTAS_GESTIONAR
from app.routers.dependencias import DatabaseSession, requiere
from app.schemas.operador import OperadorRespuesta, OperadoresPagina
from app.services import operador as service

# Iteración 2: las personas se crean junto con su cuenta de usuario (D3). Esta ruta queda solo de
# consulta y solo para el Administrador; se quitaron POST, PATCH y DELETE (D4 y D6).
router = APIRouter(prefix="/operadores", tags=["Operadores"], dependencies=[Depends(requiere(CUENTAS_GESTIONAR))])
OperatorId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.get("", response_model=OperadoresPagina)
def list_all(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> OperadoresPagina:
    return OperadoresPagina.model_validate(service.list_operators(session, offset, limit))


@router.get("/{id}", response_model=OperadorRespuesta)
def get_one(id: OperatorId, session: DatabaseSession) -> OperadorRespuesta:
    return OperadorRespuesta.model_validate(service.get_operator(session, id))
