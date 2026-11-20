from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.domain.pagos import MESES_MAXIMO, MESES_MINIMO
from app.domain.permisos import PAGOS, PAGOS_ANULAR
from app.domain.reglas import normalizar_placa
from app.routers.dependencias import DatabaseSession, Sesion, requiere
from app.schemas.pago import (
    AnulacionCrear, CotizacionRespuesta, EstadoMensualidadRespuesta, EstadoPago, MetodoPago, PagoCrear, PagoDetalle,
    PagosPagina,
)
from app.schemas.vehiculo import Placa
from app.services import pago as service

# Iteración 3: ambos roles consultan y registran pagos (D14); solo el Administrador anula.
# El responsable es la cuenta de la sesión (RF-36): nunca se recibe en el cuerpo de la solicitud.
router = APIRouter(prefix="/pagos", tags=["Pagos"], dependencies=[Depends(requiere(PAGOS))])
PagoId = Annotated[int, Path(ge=1, le=9223372036854775807)]


@router.get("/estado/{placa}", response_model=EstadoMensualidadRespuesta)
def estado(placa: Placa, session: DatabaseSession):
    return service.estado(session, placa)


@router.get("/cotizacion", response_model=CotizacionRespuesta)
def cotizar(placa: Annotated[Placa, Query()], meses: Annotated[int, Query(ge=MESES_MINIMO, le=MESES_MAXIMO)],
            session: DatabaseSession):
    return service.cotizar(session, placa, meses)


@router.post("", response_model=PagoDetalle, status_code=201)
def registrar(data: PagoCrear, session: DatabaseSession, sesion: Sesion):
    return service.registrar(session, data, sesion)


@router.get("", response_model=PagosPagina)
def listar(
    session: DatabaseSession,
    offset: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    placa: Annotated[str | None, Query(max_length=20)] = None,
    desde: date | None = None,
    hasta: date | None = None,
    metodo: MetodoPago | None = None,
    estado: EstadoPago | None = None,
):
    placa = normalizar_placa(placa) if placa and placa.strip(" -") else None
    return service.listar(session, offset, limit, placa, desde, hasta, metodo, estado)


@router.get("/{id}", response_model=PagoDetalle)
def detalle(id: PagoId, session: DatabaseSession):
    return service.detalle(session, id)


@router.post("/{id}/anular", response_model=PagoDetalle, dependencies=[Depends(requiere(PAGOS_ANULAR))])
def anular(id: PagoId, data: AnulacionCrear, session: DatabaseSession, sesion: Sesion):
    return service.anular(session, id, data, sesion)
