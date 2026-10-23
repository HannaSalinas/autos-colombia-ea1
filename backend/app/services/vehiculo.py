from functools import wraps

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.reglas import hoy_bogota, validar_placa
from app.models import Cliente, Estancia, Vehiculo
from app.schemas.vehiculo import VehiculoActualizar, VehiculoCrear, VehiculoDetalle, VehiculoRespuesta
from app.services.mensualidad import vencimientos


class VehiculoError(Exception):
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
            if code == "23505" and constraint == "uq_vehiculo_placa":
                raise VehiculoError(409, "Ya existe un vehículo con esa placa.") from None
            if code == "23503":
                raise VehiculoError(409, "El vehículo tiene registros relacionados (estancias o mensualidades) y no se puede eliminar.") from None
            if code in {"23502", "23514"}:
                raise VehiculoError(422, "Los datos incumplen las restricciones del vehículo.") from None
            raise VehiculoError(409, "La operación entra en conflicto con los datos existentes.") from None
        except SQLAlchemyError:
            session.rollback()
            raise VehiculoError(503, "No se pudo completar la operación con la base de datos.") from None
    return wrapped


def find_vehicle(session: Session, vehicle_id: int, for_update: bool = False) -> Vehiculo:
    vehicle = session.get(Vehiculo, vehicle_id, with_for_update=for_update)
    if vehicle is None:
        raise VehiculoError(404, "Vehículo no encontrado.")
    return vehicle


def ensure_client(session: Session, cliente_id: int) -> None:
    if session.get(Cliente, cliente_id) is None:
        raise VehiculoError(404, "Cliente no encontrado.")


def details(session: Session, vehicles: list[Vehiculo]) -> list[VehiculoDetalle]:
    """Agrega a cada vehículo el nombre del cliente y el estado de su mensualidad."""
    hoy = hoy_bogota()
    hasta = vencimientos(session, (v.id for v in vehicles), hoy)
    return [
        VehiculoDetalle(
            **VehiculoRespuesta.model_validate(v).model_dump(),
            cliente_nombre=v.cliente.nombre,
            mensualidad_vigente=hasta.get(v.id) is not None and hasta[v.id] >= hoy,
            mensualidad_hasta=hasta.get(v.id),
        )
        for v in vehicles
    ]


@database_operation
def create_vehicle(session: Session, data: VehiculoCrear) -> VehiculoDetalle:
    ensure_client(session, data.cliente_id)
    vehicle = Vehiculo(**data.model_dump())
    session.add(vehicle)
    session.commit()
    session.refresh(vehicle)
    return details(session, [vehicle])[0]


@database_operation
def list_vehicles(session: Session, offset: int, limit: int) -> dict:
    total = session.scalar(select(func.count()).select_from(Vehiculo))
    items = list(session.scalars(select(Vehiculo).order_by(Vehiculo.id).offset(offset).limit(limit)))
    return {"items": details(session, items), "total": total, "offset": offset, "limit": limit}


@database_operation
def get_vehicle(session: Session, vehicle_id: int) -> VehiculoDetalle:
    return details(session, [find_vehicle(session, vehicle_id)])[0]


@database_operation
def update_vehicle(session: Session, vehicle_id: int, data: VehiculoActualizar) -> VehiculoDetalle:
    # FOR UPDATE: mientras se edita, otra solicitud no puede modificar este vehículo.
    vehicle = find_vehicle(session, vehicle_id, for_update=True)
    changes = data.model_dump(exclude_unset=True)
    if "cliente_id" in changes:
        ensure_client(session, changes["cliente_id"])
    if "tipo" in changes and changes["tipo"] != vehicle.tipo and session.scalar(
        select(Estancia.id).where(Estancia.vehiculo_id == vehicle.id, Estancia.salida.is_(None))
    ) is not None:
        session.rollback()
        raise VehiculoError(409, "No se puede cambiar el tipo de un vehículo que está dentro del parqueadero.")
    try:
        # La placa debe cumplir el formato del tipo final (puede cambiar uno, el otro o ambos).
        validar_placa(changes.get("placa", vehicle.placa), changes.get("tipo", vehicle.tipo))
    except ValueError as error:
        session.rollback()
        raise VehiculoError(422, str(error)) from None
    for key, value in changes.items():
        setattr(vehicle, key, value)
    session.commit()
    session.refresh(vehicle)
    return details(session, [vehicle])[0]


@database_operation
def delete_vehicle(session: Session, vehicle_id: int) -> None:
    vehicle = find_vehicle(session, vehicle_id)
    session.delete(vehicle)
    session.commit()
