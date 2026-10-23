from typing import Annotated

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.database import get_session
from app.schemas.celda import CeldaRespuesta
from app.schemas.estancia import (
    CorreccionCrear, CorreccionRespuesta, EntradaCrear, EstadoVehiculoRespuesta, MovimientoRespuesta,
    NovedadCrear, NovedadRespuesta, SalidaCrear,
)
from app.schemas.vehiculo import Placa
from app.services.estancia import ServicioEstancia

router = APIRouter(prefix="/estancias", tags=["Estancias"])
DatabaseSession = Annotated[Session, Depends(get_session)]
EstanciaId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.post("/entrada", response_model=MovimientoRespuesta, status_code=201)
def entrada(data: EntradaCrear, session: DatabaseSession) -> MovimientoRespuesta:
    return ServicioEstancia(session).entrada(data)


@router.post("/salida", response_model=MovimientoRespuesta)
def salida(data: SalidaCrear, session: DatabaseSession) -> MovimientoRespuesta:
    return ServicioEstancia(session).salida(data)


@router.get("/vehiculo/{placa}", response_model=EstadoVehiculoRespuesta)
def consultar(placa: Placa, session: DatabaseSession) -> EstadoVehiculoRespuesta:
    return ServicioEstancia(session).consultar(placa)


@router.get("/{id}/celdas-disponibles", response_model=list[CeldaRespuesta])
def celdas_disponibles(id: EstanciaId, session: DatabaseSession) -> list[CeldaRespuesta]:
    return ServicioEstancia(session).celdas_disponibles(id)


@router.post("/{id}/correccion-celda", response_model=CorreccionRespuesta, status_code=201)
def corregir_celda(id: EstanciaId, data: CorreccionCrear, session: DatabaseSession) -> CorreccionRespuesta:
    return ServicioEstancia(session).corregir_celda(id, data)


@router.get("/{id}/correcciones", response_model=list[CorreccionRespuesta])
def correcciones(id: EstanciaId, session: DatabaseSession) -> list[CorreccionRespuesta]:
    return ServicioEstancia(session).correcciones(id)


@router.post("/{id}/novedades", response_model=NovedadRespuesta, status_code=201)
def registrar_novedad(id: EstanciaId, data: NovedadCrear, session: DatabaseSession) -> NovedadRespuesta:
    return ServicioEstancia(session).registrar_novedad(id, data)


@router.get("/{id}/novedades", response_model=list[NovedadRespuesta])
def novedades(id: EstanciaId, session: DatabaseSession) -> list[NovedadRespuesta]:
    return ServicioEstancia(session).novedades(id)
