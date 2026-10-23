"""Consulta de clientes. Crear, editar y borrar clientes es de la Iteración 2."""

from functools import wraps

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Cliente, Vehiculo
from app.schemas.vehiculo import VehiculoDetalle
from app.services.vehiculo import details


class ClienteError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def database_operation(operation):
    @wraps(operation)
    def wrapped(session: Session, *args, **kwargs):
        try:
            return operation(session, *args, **kwargs)
        except SQLAlchemyError:
            session.rollback()
            raise ClienteError(503, "No se pudo completar la operación con la base de datos.") from None
    return wrapped


def find_client(session: Session, client_id: int) -> Cliente:
    client = session.get(Cliente, client_id)
    if client is None:
        raise ClienteError(404, "Cliente no encontrado.")
    return client


@database_operation
def list_clients(session: Session, offset: int, limit: int) -> dict:
    total = session.scalar(select(func.count()).select_from(Cliente))
    items = list(session.scalars(select(Cliente).order_by(Cliente.nombre, Cliente.id).offset(offset).limit(limit)))
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@database_operation
def get_client(session: Session, client_id: int) -> Cliente:
    return find_client(session, client_id)


@database_operation
def list_client_vehicles(session: Session, client_id: int) -> list[VehiculoDetalle]:
    find_client(session, client_id)
    vehicles = list(session.scalars(select(Vehiculo).where(Vehiculo.cliente_id == client_id).order_by(Vehiculo.id)))
    return details(session, vehicles)
