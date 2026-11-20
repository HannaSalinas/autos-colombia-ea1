"""Tarifas mensuales por tipo de vehículo (D12, RF-32, RF-33).

Nunca se editan ni se borran (RNF-24): lo impide además un trigger de la base (migración 0009).
La vigente de cada tipo es la más reciente. El Administrador que la define queda en la propia fila
(D18): la tabla de tarifas es a la vez su historial.
"""

from datetime import datetime, timezone
from functools import wraps

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.pagos import TIPOS_VEHICULO
from app.models import CuentaUsuario, Operador, Tarifa
from app.schemas.tarifa import TarifaCrear, TarifaRespuesta, TarifasPagina, TarifaVigenteRespuesta
from app.services.autenticacion import SesionActual


class TarifaError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def operacion(funcion):
    @wraps(funcion)
    def envuelta(session: Session, *args, **kwargs):
        try:
            return funcion(session, *args, **kwargs)
        except IntegrityError as error:
            session.rollback()
            code = getattr(error.orig, "sqlstate", None)
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if code == "23505" and constraint == "uq_tarifa_tipo_desde":
                raise TarifaError(409, "Otra tarifa del mismo tipo se definió en el mismo instante. Intenta de "
                                       "nuevo.") from None
            if code in {"23502", "23514"}:
                raise TarifaError(422, "Los datos incumplen las restricciones de la tarifa.") from None
            raise TarifaError(409, "La operación entra en conflicto con los datos existentes.") from None
        except SQLAlchemyError:
            session.rollback()
            raise TarifaError(503, "No se pudo completar la operación con la base de datos.") from None
    return envuelta


def tarifa_vigente(session: Session, tipo_vehiculo: str) -> Tarifa | None:
    """La vigente es la más reciente del tipo: cada cambio crea una tarifa nueva desde ese momento."""
    return session.scalar(select(Tarifa).where(Tarifa.tipo_vehiculo == tipo_vehiculo)
                          .order_by(Tarifa.vigente_desde.desc(), Tarifa.id.desc()).limit(1))


def _con_autor():
    return (select(Tarifa, Operador.nombre, CuentaUsuario.nombre_usuario)
            .outerjoin(CuentaUsuario, CuentaUsuario.id == Tarifa.definida_por_cuenta_id)
            .outerjoin(Operador, Operador.id == CuentaUsuario.operador_id))


def _respuesta(fila) -> TarifaRespuesta:
    tarifa, nombre, usuario = fila
    return TarifaRespuesta(id=tarifa.id, tipo_vehiculo=tarifa.tipo_vehiculo, valor=tarifa.valor,
                           vigente_desde=tarifa.vigente_desde,
                           definida_por=f"{nombre} ({usuario})" if usuario else None)


@operacion
def vigentes(session: Session) -> list[TarifaVigenteRespuesta]:
    """RF-32: la tarifa vigente de cada tipo de vehículo, siempre en el mismo orden."""
    resultado = []
    for tipo in TIPOS_VEHICULO:
        fila = session.execute(_con_autor().where(Tarifa.tipo_vehiculo == tipo)
                               .order_by(Tarifa.vigente_desde.desc(), Tarifa.id.desc()).limit(1)).one_or_none()
        resultado.append(TarifaVigenteRespuesta(tipo_vehiculo=tipo, tarifa=_respuesta(fila) if fila else None))
    return resultado


@operacion
def historial(session: Session, offset: int, limit: int, tipo: str | None = None) -> TarifasPagina:
    """RF-32 (solo Administrador): valor, inicio de vigencia y quién la definió. Más recientes primero."""
    consulta = _con_autor()
    if tipo:
        consulta = consulta.where(Tarifa.tipo_vehiculo == tipo)
    total = session.scalar(select(func.count()).select_from(consulta.subquery()))
    filas = session.execute(consulta.order_by(Tarifa.vigente_desde.desc(), Tarifa.id.desc())
                            .offset(offset).limit(limit)).all()
    return TarifasPagina(items=[_respuesta(f) for f in filas], total=total, offset=offset, limit=limit)


@operacion
def crear(session: Session, data: TarifaCrear, actor: SesionActual) -> TarifaRespuesta:
    """RF-33: la nueva tarifa rige desde este momento (hora del servidor); los pagos ya registrados
    conservan su monto porque lo guardaron al registrarse (D11)."""
    tarifa = Tarifa(tipo_vehiculo=data.tipo_vehiculo, valor=data.valor, vigente_desde=datetime.now(timezone.utc),
                    definida_por_cuenta_id=actor.cuenta_id)
    session.add(tarifa)
    session.commit()
    return _respuesta(session.execute(_con_autor().where(Tarifa.id == tarifa.id)).one())
