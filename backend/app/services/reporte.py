"""Consultas de solo lectura: ocupación actual e historial de estancias (Fase 4)."""

from datetime import date, datetime, timezone
from functools import wraps

from sqlalchemy import Select, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, aliased

from app.domain.reglas import (
    TOTAL_CELDAS, formatear_permanencia, normalizar_placa, permanencia_segundos, rango_bogota,
)
from app.models import Celda, CorreccionCelda, Estancia, Novedad, Operador, Vehiculo
from app.schemas.reporte import (
    CeldasPorTipo, EstanciaHistorial, HistorialPagina, OcupacionRespuesta, VehiculoDentro,
)


class ReporteError(Exception):
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
            raise ReporteError(503, "No se pudo completar la consulta con la base de datos.") from None
    return wrapped


@database_operation
def ocupacion(session: Session) -> OcupacionRespuesta:
    ahora = datetime.now(timezone.utc)
    abierta = Estancia.salida.is_(None)
    # Celdas por tipo: total y ocupadas (con una estancia abierta). Solo MOTO y CARRO.
    filas = session.execute(
        select(Celda.tipo, func.count(Celda.id), func.count(Estancia.id))
        .outerjoin(Estancia, (Estancia.celda_id == Celda.id) & abierta)
        .where(Celda.tipo.in_(TOTAL_CELDAS)).group_by(Celda.tipo)
    ).all()
    conteo = {tipo: (total, ocupadas) for tipo, total, ocupadas in filas}
    celdas = []
    for tipo in ("CARRO", "MOTO"):
        total, ocupadas = conteo.get(tipo, (0, 0))
        celdas.append(CeldasPorTipo(tipo=tipo, total=total, ocupadas=ocupadas, libres=total - ocupadas))
    dentro = session.execute(
        select(Estancia, Vehiculo.placa, Vehiculo.tipo, Celda.codigo, Operador.nombre)
        .join(Vehiculo, Vehiculo.id == Estancia.vehiculo_id).join(Celda, Celda.id == Estancia.celda_id)
        .join(Operador, Operador.id == Estancia.operador_entrada_id)
        .where(abierta).order_by(Estancia.entrada, Estancia.id)
    ).all()
    return OcupacionRespuesta(
        generado=ahora, celdas=celdas,
        dentro=[
            VehiculoDentro(estancia_id=e.id, placa=placa, tipo_vehiculo=tipo, celda=codigo, entrada=e.entrada,
                           operador_entrada=operador,
                           tiempo=formatear_permanencia(permanencia_segundos(e.entrada, ahora)))
            for e, placa, tipo, codigo, operador in dentro
        ],
    )


def _filtrar(consulta: Select, placa: str | None, desde: date | None, hasta: date | None) -> Select:
    if placa:
        consulta = consulta.where(Vehiculo.placa == placa)
    inicio, fin = rango_bogota(desde, hasta)
    if inicio is not None:
        consulta = consulta.where(Estancia.entrada >= inicio)
    if fin is not None:
        consulta = consulta.where(Estancia.entrada < fin)
    return consulta


@database_operation
def historial(session: Session, placa: str | None, desde: date | None, hasta: date | None,
              offset: int, limit: int) -> HistorialPagina:
    """Estancias (abiertas y cerradas), de la más reciente a la más antigua.

    Filtros: placa exacta (normalizada) y rango de días de Bogotá sobre la fecha de ENTRADA.
    """
    try:
        placa = normalizar_placa(placa) if placa and placa.strip(" -") else None
        rango_bogota(desde, hasta)
    except ValueError as error:
        raise ReporteError(422, str(error)) from None
    salida_op = aliased(Operador)
    entrada_op = aliased(Operador)
    novedades = select(func.count(Novedad.id)).where(Novedad.estancia_id == Estancia.id).scalar_subquery()
    correcciones = (select(func.count(CorreccionCelda.id))
                    .where(CorreccionCelda.estancia_id == Estancia.id).scalar_subquery())
    base = select(Estancia.id).join(Vehiculo, Vehiculo.id == Estancia.vehiculo_id)
    total = session.scalar(select(func.count()).select_from(_filtrar(base, placa, desde, hasta).subquery()))
    consulta = _filtrar(
        select(Estancia, Vehiculo.placa, Vehiculo.tipo, Celda.codigo, entrada_op.nombre, salida_op.nombre,
               novedades, correcciones)
        .join(Vehiculo, Vehiculo.id == Estancia.vehiculo_id).join(Celda, Celda.id == Estancia.celda_id)
        .join(entrada_op, entrada_op.id == Estancia.operador_entrada_id)
        .outerjoin(salida_op, salida_op.id == Estancia.operador_salida_id),
        placa, desde, hasta,
    ).order_by(Estancia.entrada.desc(), Estancia.id.desc()).offset(offset).limit(limit)
    items = []
    for e, placa_v, tipo, codigo, op_entrada, op_salida, n_nov, n_corr in session.execute(consulta):
        segundos = permanencia_segundos(e.entrada, e.salida) if e.salida else None
        items.append(EstanciaHistorial(
            id=e.id, placa=placa_v, tipo_vehiculo=tipo, celda=codigo, entrada=e.entrada, salida=e.salida,
            abierta=e.salida is None, duracion_segundos=segundos,
            permanencia=formatear_permanencia(segundos) if segundos is not None else None,
            operador_entrada=op_entrada, operador_salida=op_salida, novedades=n_nov, correcciones=n_corr,
        ))
    return HistorialPagina(items=items, total=total, offset=offset, limit=limit)
