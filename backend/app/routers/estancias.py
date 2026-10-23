from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_session
from app.schemas.estancia import EntradaCrear, SalidaCrear, EstadoVehiculoRespuesta, MovimientoRespuesta
from app.schemas.vehiculo import Placa
from app.services.estancia import ServicioEstancia

router = APIRouter(prefix="/estancias", tags=["Estancias"])
DatabaseSession = Annotated[Session, Depends(get_session)]


@router.post("/entrada", response_model=MovimientoRespuesta, status_code=201)
def entrada(data: EntradaCrear, session: DatabaseSession) -> MovimientoRespuesta:
    return ServicioEstancia(session).entrada(data)


@router.post("/salida", response_model=MovimientoRespuesta)
def salida(data: SalidaCrear, session: DatabaseSession) -> MovimientoRespuesta:
    return ServicioEstancia(session).salida(data)


@router.get("/vehiculo/{placa}", response_model=EstadoVehiculoRespuesta)
def consultar(placa: Placa, session: DatabaseSession) -> EstadoVehiculoRespuesta:
    return ServicioEstancia(session).consultar(placa)
