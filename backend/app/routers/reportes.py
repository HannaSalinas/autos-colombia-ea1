from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_session
from app.domain.permisos import CONSULTAS, RECAUDO_VER
from app.routers.dependencias import requiere
from app.schemas.pago import RecaudoRespuesta
from app.schemas.reporte import HistorialPagina, OcupacionRespuesta
from app.services import pago as pagos
from app.services import reporte as service

router = APIRouter(prefix="/reportes", tags=["Reportes"], dependencies=[Depends(requiere(CONSULTAS))])
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


@router.get("/recaudo", response_model=RecaudoRespuesta, dependencies=[Depends(requiere(RECAUDO_VER))])
def recaudo(
    session: DatabaseSession,
    desde: Annotated[date, Query(description="Día de Bogotá (AAAA-MM-DD), incluido")],
    hasta: Annotated[date, Query(description="Día de Bogotá (AAAA-MM-DD), incluido")],
):
    """Iteración 3 (RF-39, solo Administrador): total recaudado en pagos válidos por método y por tipo
    de vehículo, y los anulados aparte. Ambos se cuentan por la fecha del pago."""
    return pagos.recaudo(session, desde, hasta)
