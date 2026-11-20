"""Clientes. Iteración 3 (RF-34, D15): el Administrador registra y ambos roles consultan, buscando por
nombre o documento. Sin edición ni eliminación en esta iteración (D17)."""

from datetime import datetime, timezone
from functools import wraps

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Cliente, CuentaUsuario, Operador, Vehiculo
from app.schemas.cliente import ClienteCrear, ClienteRespuesta, ClientesPagina, VehiculoDelCliente
from app.schemas.vehiculo import VehiculoDetalle
from app.services.autenticacion import SesionActual
from app.services.vehiculo import details


class ClienteError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def documento_repetido(tipo: str, documento: str) -> str:
    return f"Ya existe un cliente con el documento {tipo} {documento}."


def database_operation(operation):
    @wraps(operation)
    def wrapped(session: Session, *args, **kwargs):
        try:
            return operation(session, *args, **kwargs)
        except ClienteError:
            session.rollback()
            raise
        except IntegrityError as error:
            session.rollback()
            code = getattr(error.orig, "sqlstate", None)
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            # Dos registros simultáneos del mismo documento: el índice único deja solo uno (HU-28).
            if code == "23505" and constraint == "uq_cliente_tipo_documento":
                data = args[0] if args else None
                detalle = documento_repetido(data.tipo_documento, data.documento) if isinstance(data, ClienteCrear) \
                    else "Ya existe un cliente con ese tipo y número de documento."
                raise ClienteError(409, detalle) from None
            if code in {"23502", "23514"}:
                raise ClienteError(422, "Los datos incumplen las restricciones del cliente.") from None
            raise ClienteError(409, "La operación entra en conflicto con los datos existentes.") from None
        except SQLAlchemyError:
            session.rollback()
            raise ClienteError(503, "No se pudo completar la operación con la base de datos.") from None
    return wrapped


def find_client(session: Session, client_id: int) -> Cliente:
    client = session.get(Cliente, client_id)
    if client is None:
        raise ClienteError(404, "Cliente no encontrado.")
    return client


def _escapar(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _consulta():
    return (select(Cliente, Operador.nombre, CuentaUsuario.nombre_usuario)
            .outerjoin(CuentaUsuario, CuentaUsuario.id == Cliente.registrado_por_cuenta_id)
            .outerjoin(Operador, Operador.id == CuentaUsuario.operador_id))


def _respuestas(session: Session, filas) -> list[ClienteRespuesta]:
    """Agrega a cada cliente sus vehículos con una sola consulta."""
    ids = [cliente.id for cliente, *_ in filas]
    vehiculos: dict[int, list[VehiculoDelCliente]] = {}
    if ids:
        for v in session.scalars(select(Vehiculo).where(Vehiculo.cliente_id.in_(ids)).order_by(Vehiculo.placa)):
            vehiculos.setdefault(v.cliente_id, []).append(VehiculoDelCliente(id=v.id, placa=v.placa, tipo=v.tipo))
    return [
        ClienteRespuesta(id=c.id, tipo_documento=c.tipo_documento, documento=c.documento, nombre=c.nombre,
                         telefono=c.telefono, correo=c.correo, registrado_en=c.registrado_en,
                         registrado_por=f"{nombre} ({usuario})" if usuario else None,
                         vehiculos=vehiculos.get(c.id, []))
        for c, nombre, usuario in filas
    ]


@database_operation
def list_clients(session: Session, offset: int, limit: int, buscar: str | None = None) -> ClientesPagina:
    """RF-34: busca por parte del nombre (sin distinguir mayúsculas) o del número de documento."""
    consulta = _consulta()
    if buscar and buscar.strip():
        patron = f"%{_escapar(buscar.strip())}%"
        consulta = consulta.where(or_(Cliente.nombre.ilike(patron, escape="\\"),
                                      Cliente.documento.ilike(patron, escape="\\")))
    total = session.scalar(select(func.count()).select_from(consulta.subquery()))
    filas = session.execute(consulta.order_by(Cliente.nombre, Cliente.id).offset(offset).limit(limit)).all()
    return ClientesPagina(items=_respuestas(session, filas), total=total, offset=offset, limit=limit)


def _uno(session: Session, client_id: int) -> ClienteRespuesta:
    fila = session.execute(_consulta().where(Cliente.id == client_id)).one_or_none()
    if fila is None:
        raise ClienteError(404, "Cliente no encontrado.")
    return _respuestas(session, [fila])[0]


@database_operation
def get_client(session: Session, client_id: int) -> ClienteRespuesta:
    return _uno(session, client_id)


@database_operation
def create_client(session: Session, data: ClienteCrear, actor: SesionActual) -> ClienteRespuesta:
    """RF-34. La revisión previa da el mensaje claro; si dos registros simultáneos pasan la revisión,
    el índice único uq_cliente_tipo_documento deja solo uno y el otro recibe el mismo 409."""
    if session.scalar(select(Cliente.id).where(Cliente.tipo_documento == data.tipo_documento,
                                               func.upper(Cliente.documento) == data.documento)) is not None:
        raise ClienteError(409, documento_repetido(data.tipo_documento, data.documento))
    cliente = Cliente(**data.model_dump(), registrado_en=datetime.now(timezone.utc),
                      registrado_por_cuenta_id=actor.cuenta_id)
    session.add(cliente)
    session.commit()
    return _uno(session, cliente.id)


@database_operation
def list_client_vehicles(session: Session, client_id: int) -> list[VehiculoDetalle]:
    find_client(session, client_id)
    vehicles = list(session.scalars(select(Vehiculo).where(Vehiculo.cliente_id == client_id).order_by(Vehiculo.id)))
    return details(session, vehicles)
