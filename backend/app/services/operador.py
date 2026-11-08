"""Consulta de personas. Iteración 2: se crean junto con su cuenta; aquí ya no se crean, editan ni borran."""

from functools import wraps

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Operador


class OperadorError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def database_operation(operation):
    """Centraliza rollback y mensajes públicos sin detalles del driver."""
    @wraps(operation)
    def wrapped(session: Session, *args, **kwargs):
        try:
            return operation(session, *args, **kwargs)
        except SQLAlchemyError:
            session.rollback()
            raise OperadorError(503, "No se pudo completar la operación con la base de datos.") from None
    return wrapped


def find_operator(session: Session, operator_id: int) -> Operador:
    operator = session.get(Operador, operator_id)
    if operator is None:
        raise OperadorError(404, "Operador no encontrado.")
    return operator


@database_operation
def list_operators(session: Session, offset: int, limit: int) -> dict:
    total = session.scalar(select(func.count()).select_from(Operador))
    items = list(session.scalars(select(Operador).order_by(Operador.id).offset(offset).limit(limit)))
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@database_operation
def get_operator(session: Session, operator_id: int) -> Operador:
    return find_operator(session, operator_id)
