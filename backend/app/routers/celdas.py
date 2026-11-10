from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query

from app.domain.permisos import CELDAS_GESTIONAR, CELDAS_VER
from app.routers.dependencias import DatabaseSession, requiere
from app.schemas.celda import CeldaActualizar, CeldaCrear, CeldaDetalle, CeldaGestion, CeldasPagina
from app.services import celda as service
from app.services.autenticacion import SesionActual

# Iteración 2: ambos roles consultan; solo el Administrador las gestiona. No hay DELETE: las celdas
# nunca se borran, se inhabilitan (D4, RNF-18).
router = APIRouter(prefix="/celdas", tags=["Celdas"], dependencies=[Depends(requiere(CELDAS_VER))])
Administrador = Annotated[SesionActual, Depends(requiere(CELDAS_GESTIONAR))]
CellId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.post("", response_model=CeldaGestion, status_code=201)
def create(data: CeldaCrear, session: DatabaseSession, actor: Administrador) -> CeldaGestion:
    return service.create_cell(session, data, actor)


@router.get("", response_model=CeldasPagina)
def list_all(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    buscar: Annotated[str | None, Query(max_length=10, description="Parte del código")] = None,
    tipo: Literal["MOTO", "CARRO"] | None = None,
    estado: Literal["LIBRE", "OCUPADA", "INHABILITADA"] | None = None,
) -> CeldasPagina:
    return service.list_cells(session, offset, limit, buscar, tipo, estado)


@router.get("/{id}", response_model=CeldaDetalle)
def get_one(id: CellId, session: DatabaseSession) -> CeldaDetalle:
    return service.get_cell(session, id)


@router.patch("/{id}", response_model=CeldaGestion)
def update(id: CellId, data: CeldaActualizar, session: DatabaseSession, actor: Administrador) -> CeldaGestion:
    return service.update_cell(session, id, data, actor)


@router.post("/{id}/inhabilitar", response_model=CeldaGestion)
def disable(id: CellId, session: DatabaseSession, actor: Administrador) -> CeldaGestion:
    return service.disable_cell(session, id, actor)


@router.post("/{id}/rehabilitar", response_model=CeldaGestion)
def enable(id: CellId, session: DatabaseSession, actor: Administrador) -> CeldaGestion:
    return service.enable_cell(session, id, actor)
