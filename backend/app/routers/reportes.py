from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_session
from app.schemas.reporte import HistorialPagina, OcupacionRespuesta
from app.services import reporte as service

router = APIRouter(prefix="/reportes", tags=["Reportes"])
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.get("/ocupacion", response_model=OcupacionRespuesta)
def ocupacion(session: DatabaseSession):
    """Vehículos dentro (placa, tipo, celda, hora de entrada) y celdas libres por tipo."""
    return service.ocupacion(session)


@router.get("/historial", response_model=HistorialPagina)
def historial(
    session: DatabaseSession,
    placa: Annotated[str | None, Query(max_length=20)] = None,
    desde: Annotated[date | None, Query(description="Día de Bogotá (AAAA-MM-DD), incluido")] = None,
    hasta: Annotated[date | None, Query(description="Día de Bogotá (AAAA-MM-DD), incluido")] = None,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """Historial de estancias filtrable por placa y por fecha de entrada. Nunca se borra."""
    return service.historial(session, placa, desde, hasta, offset, limit)
