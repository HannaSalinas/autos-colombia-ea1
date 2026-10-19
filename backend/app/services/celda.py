from functools import wraps

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Celda
from app.schemas.celda import CeldaActualizar, CeldaCrear


class CeldaError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def database_operation(operation):
    """Centraliza rollback y mensajes públicos sin detalles del driver."""
    @wraps(operation)
    def wrapped(session: Session, *args, **kwargs):
        try:
            return operation(session, *args, **kwargs)
        except IntegrityError as error:
            session.rollback()
            code = getattr(error.orig, "sqlstate", None)
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if code == "23505" and constraint == "uq_celda_codigo":
                raise CeldaError(409, "Ya existe una celda con ese código.") from None
            if code == "23503":
                raise CeldaError(409, "La celda tiene registros relacionados y no se puede eliminar.") from None
            if code in {"23502", "23514"}:
                raise CeldaError(422, "Los datos incumplen las restricciones de la celda.") from None
            raise CeldaError(409, "La operación entra en conflicto con los datos existentes.") from None
        except SQLAlchemyError:
            session.rollback()
            raise CeldaError(503, "No se pudo completar la operación con la base de datos.") from None
    return wrapped


def find_cell(session: Session, cell_id: int) -> Celda:
    cell = session.get(Celda, cell_id)
    if cell is None:
        raise CeldaError(404, "Celda no encontrada.")
    return cell


@database_operation
def create_cell(session: Session, data: CeldaCrear) -> Celda:
    cell = Celda(**data.model_dump())
    session.add(cell)
    session.commit()
    session.refresh(cell)
    return cell


@database_operation
def list_cells(session: Session, offset: int, limit: int) -> dict:
    total = session.scalar(select(func.count()).select_from(Celda))
    items = list(session.scalars(select(Celda).order_by(Celda.id).offset(offset).limit(limit)))
    return {"items": items, "total": total, "offset": offset, "limit": limit}


@database_operation
def get_cell(session: Session, cell_id: int) -> Celda:
    return find_cell(session, cell_id)


@database_operation
def update_cell(session: Session, cell_id: int, data: CeldaActualizar) -> Celda:
    cell = find_cell(session, cell_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(cell, key, value)
    session.commit()
    session.refresh(cell)
    return cell


@database_operation
def delete_cell(session: Session, cell_id: int) -> None:
    cell = find_cell(session, cell_id)
    session.delete(cell)
    session.commit()


