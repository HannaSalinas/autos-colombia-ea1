from collections.abc import Iterable
from datetime import date

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.domain.reglas import hoy_bogota, mensualidad_vigente
from app.models import Mensualidad, Pago
from app.schemas.mensualidad import MensualidadRespuesta


def periodo_valido() -> ColumnElement[bool]:
    """El periodo cuenta para la vigencia si no está anulado (Iteración 3, RF-38).

    Los periodos anteriores a la Iteración 3 no tienen pago (pago_estado NULL) y siguen siendo
    válidos (D10). Es la ÚNICA definición: la usan la entrada, el listado de vehículos, el estado de
    la mensualidad, los pagos y la demostración.
    """
    return or_(Mensualidad.pago_estado.is_(None), Mensualidad.pago_estado == "VALIDO")


def vencimientos(session: Session, vehiculo_ids: Iterable[int], hoy: date) -> dict[int, date]:
    """Para cada vehículo, la fecha_fin más lejana de las mensualidades que ya comenzaron (sin anuladas).

    Es la misma regla de app.domain.reglas.mensualidad_vigente escrita en SQL: si esa fecha
    es >= hoy, existe una mensualidad con inicio <= hoy <= fin.
    """
    ids = list(vehiculo_ids)
    if not ids:
        return {}
    rows = session.execute(
        select(Mensualidad.vehiculo_id, func.max(Mensualidad.fecha_fin))
        .where(Mensualidad.vehiculo_id.in_(ids), Mensualidad.fecha_inicio <= hoy, periodo_valido())
        .group_by(Mensualidad.vehiculo_id)
    )
    return {vehiculo_id: hasta for vehiculo_id, hasta in rows}


def proximas(session: Session, vehiculo_ids: Iterable[int], hoy: date) -> dict[int, date]:
    """Para cada vehículo, el inicio más cercano de una mensualidad que todavía no empieza."""
    ids = list(vehiculo_ids)
    if not ids:
        return {}
    rows = session.execute(
        select(Mensualidad.vehiculo_id, func.min(Mensualidad.fecha_inicio))
        .where(Mensualidad.vehiculo_id.in_(ids), Mensualidad.fecha_inicio > hoy, periodo_valido())
        .group_by(Mensualidad.vehiculo_id)
    )
    return {vehiculo_id: inicio for vehiculo_id, inicio in rows}


def listar_de_vehiculo(session: Session, vehiculo_id: int) -> list[MensualidadRespuesta]:
    hoy = hoy_bogota()
    # Iteración 3: todos los periodos, también los anulados (el historial nunca se oculta), con su comprobante.
    filas = session.execute(
        select(Mensualidad, Pago.comprobante).outerjoin(Pago, Pago.id == Mensualidad.pago_id)
        .where(Mensualidad.vehiculo_id == vehiculo_id).order_by(Mensualidad.fecha_inicio.desc(), Mensualidad.id.desc())
    )
    return [
        MensualidadRespuesta(
            id=m.id, vehiculo_id=m.vehiculo_id, fecha_inicio=m.fecha_inicio, fecha_fin=m.fecha_fin,
            vigente=m.pago_estado != "ANULADO" and mensualidad_vigente(m.fecha_inicio, m.fecha_fin, hoy),
            comprobante=comprobante, pago_estado=m.pago_estado,
        )
        for m, comprobante in filas
    ]
